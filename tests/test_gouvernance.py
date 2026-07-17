"""Tests de la gouvernance des regles.

Deux volets :
  1. Workflow Maker-Checker : un administrateur propose, un SECOND confirme.
  2. Application TRANSACTIONNELLE : confirmation + ecriture des regles +
     versionnement + audit reussissent ensemble, ou sont toutes annulees.

Le volet transactionnel est verifie en injectant une panne a chaque etape
faillible et en controlant qu'apres l'echec, TOUT est revenu a l'etat initial
(regles inchangees a l'octet pres, proposition toujours EN_ATTENTE, aucune
version orpheline).
"""
from __future__ import annotations

import json
import os
import sys

from _outils import ModulesRediriges, Resultats, dossier_temporaire

from gouvernance import application_regles, versions, workflow_seuils

ADMIN1 = {"identifiant": "admin1", "nom": "Admin 1", "role": "admin"}
ADMIN2 = {"identifiant": "admin2", "nom": "Admin 2", "role": "admin"}

REGLES_INITIALES = {"marches": {"PART": {"libelle": "Particuliers", "regles": []}},
                    "listes_professions": {}, "meta": {"version": "1.0.0"}}
REGLES_MODIFIEES = {"marches": {"PART": {"libelle": "Particuliers", "regles": []}},
                    "listes_professions": {}, "meta": {"version": "2.0.0"}}


def _audit_factice(journal: list):
    def enregistrer(*args, **kwargs):
        journal.append(args)
    return enregistrer


def _audit_qui_echoue(*args, **kwargs):
    raise RuntimeError("panne simulee du journal d'audit")


def run() -> bool:
    r = Resultats("gouvernance : Maker-Checker & transactionnel")
    tmp = dossier_temporaire()
    chemin_regles = os.path.join(tmp, "regles.json")
    with open(chemin_regles, "w", encoding="utf-8") as f:
        json.dump(REGLES_INITIALES, f, ensure_ascii=False, indent=2)
    empreinte_initiale = open(chemin_regles, "rb").read()

    with ModulesRediriges(
        (workflow_seuils, "CHEMIN_WORKFLOW", os.path.join(tmp, "propositions.sqlite3")),
        (versions, "DOSSIER_VERSIONS", os.path.join(tmp, "versions")),
        (versions, "CHEMIN_MANIFESTE", os.path.join(tmp, "versions", "manifeste.json")),
    ):
        # ================================================================= #
        # 1. Workflow Maker-Checker
        # ================================================================= #
        id_prop = workflow_seuils.proposer(ADMIN1, REGLES_MODIFIEES, "Hausse du seuil Affluent")
        r.verifier("une proposition est creee", isinstance(id_prop, int) and id_prop > 0)
        r.egal("  statut initial EN_ATTENTE",
               workflow_seuils.obtenir(id_prop)["statut"], "EN_ATTENTE")
        r.egal("  elle apparait dans les propositions en attente",
               len(workflow_seuils.lister_en_attente()), 1)

        # Regle centrale : separation des taches.
        ok, msg, regles = workflow_seuils.confirmer(id_prop, ADMIN1)
        r.verifier("SEPARATION DES TACHES : le proposant ne peut pas confirmer", not ok)
        r.verifier("  aucune regle renvoyee dans ce cas", regles is None)
        r.egal("  la proposition reste EN_ATTENTE",
               workflow_seuils.obtenir(id_prop)["statut"], "EN_ATTENTE")

        ok, msg, regles = workflow_seuils.confirmer(id_prop, ADMIN2)
        r.verifier("un SECOND administrateur peut confirmer", ok)
        r.egal("  les regles proposees sont renvoyees", regles["meta"]["version"], "2.0.0")
        r.egal("  statut VALIDEE", workflow_seuils.obtenir(id_prop)["statut"], "VALIDEE")
        r.egal("  confirme_par trace", workflow_seuils.obtenir(id_prop)["confirme_par"], "admin2")

        ok, msg, _ = workflow_seuils.confirmer(id_prop, ADMIN2)
        r.verifier("une proposition deja traitee ne peut pas etre reconfirmee", not ok)

        id_rejet = workflow_seuils.proposer(ADMIN1, REGLES_MODIFIEES, "A rejeter")
        ok, msg = workflow_seuils.rejeter(id_rejet, ADMIN2)
        r.verifier("une proposition peut etre rejetee", ok)
        r.egal("  statut REJETEE", workflow_seuils.obtenir(id_rejet)["statut"], "REJETEE")
        r.egal("  les rejets sortent de la file d'attente",
               len(workflow_seuils.lister_en_attente()), 0)

        # ================================================================= #
        # 2. Application transactionnelle : cas nominal
        # ================================================================= #
        id_ok = workflow_seuils.proposer(ADMIN1, REGLES_MODIFIEES, "Changement valide")
        trace_audit = []
        ok, msg, version_id = application_regles.appliquer_proposition(
            id_ok, ADMIN2, _audit_factice(trace_audit), chemin_regles=chemin_regles,
        )
        r.verifier("application nominale -> succes", ok, msg)
        r.egal("  le fichier de regles contient bien la nouvelle version",
               json.load(open(chemin_regles, encoding="utf-8"))["meta"]["version"], "2.0.0")
        r.egal("  la proposition est VALIDEE",
               workflow_seuils.obtenir(id_ok)["statut"], "VALIDEE")
        r.verifier("  une version est archivee", version_id is not None
                   and os.path.exists(os.path.join(versions.DOSSIER_VERSIONS, version_id)))
        r.egal("  le journal d'audit a recu une entree", len(trace_audit), 1)
        r.egal("  l'action tracee est MODIF_SEUIL", trace_audit[0][0], "MODIF_SEUIL")

        # Remise a l'etat initial pour les tests de panne.
        with open(chemin_regles, "wb") as f:
            f.write(empreinte_initiale)

        # ================================================================= #
        # 3. Application transactionnelle : PANNE DE L'AUDIT -> rollback
        # ================================================================= #
        versions_avant = len(versions.lister_versions())
        id_panne = workflow_seuils.proposer(ADMIN1, REGLES_MODIFIEES, "Changement qui va echouer")

        ok, msg, version_id = application_regles.appliquer_proposition(
            id_panne, ADMIN2, _audit_qui_echoue, chemin_regles=chemin_regles,
        )
        r.verifier("panne du journal d'audit -> echec signale", not ok)
        r.verifier("  message explicite ('aucune modification')",
                   "aucune modification" in msg.lower())
        r.egal("  ROLLBACK : le fichier de regles est inchange a l'octet pres",
               open(chemin_regles, "rb").read(), empreinte_initiale)
        r.egal("  ROLLBACK : la proposition est revenue EN_ATTENTE",
               workflow_seuils.obtenir(id_panne)["statut"], "EN_ATTENTE")
        r.verifier("  ROLLBACK : confirme_par efface",
                   workflow_seuils.obtenir(id_panne)["confirme_par"] is None)
        r.egal("  ROLLBACK : aucune version orpheline conservee",
               len(versions.lister_versions()), versions_avant)
        r.verifier("  aucun fichier temporaire laisse derriere",
                   not os.path.exists(chemin_regles + ".tmp")
                   and not os.path.exists(chemin_regles + ".backup"))

        # La proposition rejouable : le rollback laisse le systeme utilisable.
        trace_audit = []
        ok, msg, version_id = application_regles.appliquer_proposition(
            id_panne, ADMIN2, _audit_factice(trace_audit), chemin_regles=chemin_regles,
        )
        r.verifier("apres rollback, la meme proposition peut etre rejouee avec succes", ok, msg)
        r.egal("  et les regles sont cette fois appliquees",
               json.load(open(chemin_regles, encoding="utf-8"))["meta"]["version"], "2.0.0")
        with open(chemin_regles, "wb") as f:
            f.write(empreinte_initiale)

        # ================================================================= #
        # 4. Panne du versionnement -> rollback
        # ================================================================= #
        id_panne2 = workflow_seuils.proposer(ADMIN1, REGLES_MODIFIEES, "Panne versionnement")

        def _version_qui_echoue(*args, **kwargs):
            raise OSError("disque plein (simule)")

        with ModulesRediriges((versions, "enregistrer_version", _version_qui_echoue)):
            ok, msg, _ = application_regles.appliquer_proposition(
                id_panne2, ADMIN2, _audit_factice([]), chemin_regles=chemin_regles,
            )
        r.verifier("panne du versionnement -> echec signale", not ok)
        r.egal("  ROLLBACK : regles inchangees",
               open(chemin_regles, "rb").read(), empreinte_initiale)
        r.egal("  ROLLBACK : proposition revenue EN_ATTENTE",
               workflow_seuils.obtenir(id_panne2)["statut"], "EN_ATTENTE")

        # ================================================================= #
        # 5. Refus metier : pas de rollback a faire, rien n'a ete touche
        # ================================================================= #
        id_refus = workflow_seuils.proposer(ADMIN1, REGLES_MODIFIEES, "Auto-confirmation")
        ok, msg, _ = application_regles.appliquer_proposition(
            id_refus, ADMIN1, _audit_factice([]), chemin_regles=chemin_regles,
        )
        r.verifier("auto-confirmation refusee jusque dans le chemin transactionnel", not ok)
        r.egal("  regles inchangees", open(chemin_regles, "rb").read(), empreinte_initiale)
        r.egal("  proposition toujours EN_ATTENTE",
               workflow_seuils.obtenir(id_refus)["statut"], "EN_ATTENTE")

        # ================================================================= #
        # 6. Ecriture atomique du fichier de regles
        # ================================================================= #
        application_regles._ecrire_regles_atomiquement(REGLES_MODIFIEES, chemin_regles)
        r.verifier("ecriture atomique : aucun .tmp residuel",
                   not os.path.exists(chemin_regles + ".tmp"))
        r.egal("  contenu correct",
               json.load(open(chemin_regles, encoding="utf-8"))["meta"]["version"], "2.0.0")

        # Les primitives de rollback ne sont pas exposees comme API metier.
        import gouvernance
        exposes = [n for n in ("rouvrir", "supprimer_version") if n in gouvernance.__all__]
        r.egal("les primitives de rollback ne sont pas exposees dans l'API publique",
               exposes, [])

    return r.bilan()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
