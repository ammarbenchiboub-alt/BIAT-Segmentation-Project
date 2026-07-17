"""
Application TRANSACTIONNELLE d'une proposition de changement de regles.

Probleme resolu
---------------
La page Parametrage enchainait auparavant, directement dans app.py, trois
operations independantes :

    1. confirmation de la proposition (statut -> VALIDEE)
    2. ecriture de config/regles_segmentation.json
    3. enregistrement de la version + ecriture du journal d'audit

Chacune pouvait echouer sans annuler les precedentes. Un disque plein, un
fichier verrouille par un antivirus ou un arret de l'application au mauvais
moment laissaient un etat INCOHERENT, par exemple :
    - proposition marquee VALIDEE mais regles jamais appliquees ;
    - regles appliquees mais aucune version conservee (rollback impossible) ;
    - regles appliquees mais aucune trace dans le journal d'audit -- soit
      exactement le scenario qu'un controle interne bancaire doit exclure.

Solution
--------
Une seule fonction, appliquer_proposition(), execute les etapes dans un ordre
choisi et empile pour chacune son action d'annulation. A la moindre exception,
les annulations sont rejouees en sens inverse et le systeme revient A SON ETAT
INITIAL EXACT : soit tout reussit, soit rien n'est applique.

Ordre des etapes (l'ordre n'est pas arbitraire)
-----------------------------------------------
    1. confirmer la proposition        -> annulable (rouvrir)
    2. ecrire le fichier de regles     -> annulable (restauration de l'octet
                                          pres du contenu precedent)
    3. enregistrer la version          -> annulable (supprimer_version)
    4. ecrire le journal d'audit       -> NON annulable (append-only)

Le journal d'audit est DELIBEREMENT en dernier : c'est la seule etape
irreversible (le journal n'expose aucune suppression, par conception). Toute
etape faillible doit donc etre tentee avant lui. S'il echoue, les trois
precedentes sont annulees et l'operation entiere est sans effet -- il ne reste
alors aucune modification a tracer, donc aucune trace manquante.

Ce module ne contient AUCUNE logique de segmentation : il orchestre des
ecritures de fichiers et d'etats. Le contenu des regles lui est opaque.
"""
from __future__ import annotations

import json
import os
import shutil
from typing import Any, Callable

from core.rules_loader import CHEMIN_REGLES

from . import versions as _versions
from . import workflow_seuils as _workflow


def _ecrire_regles_atomiquement(regles: dict, chemin: str) -> None:
    """Ecrit le fichier de regles de facon atomique.

    Passe par un fichier temporaire puis os.replace (atomique au niveau du
    systeme de fichiers) : une coupure pendant l'ecriture laisse l'ancien
    fichier intact, jamais un JSON tronque -- qui rendrait l'application
    entierement inutilisable, puisque le moteur ne pourrait plus charger ses
    regles."""
    temporaire = chemin + ".tmp"
    with open(temporaire, "w", encoding="utf-8") as f:
        json.dump(regles, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporaire, chemin)


def appliquer_proposition(
    id_proposition: int,
    utilisateur: dict[str, Any],
    enregistrer_audit: Callable[..., Any],
    chemin_regles: str | None = None,
) -> tuple[bool, str, str | None]:
    """Confirme et applique une proposition, de facon tout-ou-rien.

    Parametres
    ----------
    id_proposition : id de la proposition EN_ATTENTE a appliquer.
    utilisateur    : administrateur qui confirme (doit etre different du
                     proposant -- controle delegue a workflow_seuils.confirmer).
    enregistrer_audit : fonction de journalisation (injectee plutot
                     qu'importee, pour que ce module reste testable sans
                     toucher au vrai journal d'audit, et pour eviter un
                     couplage en dur gouvernance -> audit).
    chemin_regles  : chemin alternatif du fichier de regles (tests).

    Renvoie (succes, message, version_id).
    """
    chemin_regles = chemin_regles or CHEMIN_REGLES
    annulations: list[Callable[[], None]] = []

    # Sauvegarde de l'etat initial du fichier de regles, AVANT toute
    # modification. Copie sur disque (et non seulement en memoire) pour que la
    # restauration reste possible meme si le processus manque de memoire.
    sauvegarde = chemin_regles + ".backup"
    contenu_initial: bytes | None = None
    if os.path.exists(chemin_regles):
        with open(chemin_regles, "rb") as f:
            contenu_initial = f.read()
        shutil.copy2(chemin_regles, sauvegarde)

    def _restaurer_regles() -> None:
        if contenu_initial is not None:
            with open(chemin_regles, "wb") as f:
                f.write(contenu_initial)
                f.flush()
                os.fsync(f.fileno())
        elif os.path.exists(chemin_regles):
            os.remove(chemin_regles)

    try:
        # --- Etape 1 : confirmation de la proposition ---------------------
        ok, message, regles = _workflow.confirmer(id_proposition, utilisateur)
        if not ok or regles is None:
            # Refus metier (proposition deja traitee, auto-confirmation...) :
            # ce n'est pas une erreur technique, rien n'a encore ete modifie.
            return False, message, None
        annulations.append(lambda: _workflow.rouvrir(id_proposition))

        # --- Etape 2 : ecriture du fichier de regles ----------------------
        _ecrire_regles_atomiquement(regles, chemin_regles)
        annulations.append(_restaurer_regles)

        # --- Etape 3 : versionnement --------------------------------------
        proposition = _workflow.obtenir(id_proposition)
        description = proposition["description"] if proposition else ""
        version_id = _versions.enregistrer_version(
            regles, utilisateur, description, proposition_id=id_proposition,
        )
        annulations.append(lambda: _versions.supprimer_version(version_id))

        # --- Etape 4 : journal d'audit (irreversible -> en dernier) --------
        enregistrer_audit(
            "MODIF_SEUIL", utilisateur,
            {"Marche": "SYSTEME", "Description": description,
             "Proposition_id": id_proposition,
             "Propose_par": proposition["propose_par"] if proposition else "?",
             "Version_id": version_id},
            None, None, f"PROPOSITION_{id_proposition}",
        )

    except Exception as exc:  # noqa: BLE001 - on rattrape tout pour pouvoir annuler
        # Rollback en sens inverse. Chaque annulation est protegee : l'echec de
        # l'une ne doit pas empecher les autres de s'executer, sous peine de
        # laisser un etat encore plus incoherent que l'erreur d'origine.
        erreurs_rollback = []
        for annuler in reversed(annulations):
            try:
                annuler()
            except Exception as err_rollback:  # noqa: BLE001 # pragma: no cover
                erreurs_rollback.append(str(err_rollback))
        detail = f" (erreurs pendant l'annulation : {'; '.join(erreurs_rollback)})" if erreurs_rollback else ""
        return False, (
            f"Echec de l'application du changement : {exc}. Aucune modification n'a ete "
            f"appliquee, le systeme est revenu a son etat initial{detail}."
        ), None
    finally:
        if os.path.exists(sauvegarde):
            os.remove(sauvegarde)

    return True, (
        f"Proposition #{id_proposition} confirmee et appliquee (version {version_id})."
    ), version_id
