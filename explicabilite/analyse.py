"""
EXPLICABILITE DE LA DECISION DE SEGMENTATION.

Ce module repond a deux questions que le conseiller se pose devant un resultat :

    1. « Pourquoi ce segment ? »  -> parcours_decision()
       Reconstitue le cheminement complet du moteur : quelles regles ont ete
       evaluees, laquelle l'emporte, et quel est le statut de chacune des
       autres.

    2. « Que faudrait-il pour changer de segment ? » -> ecarts_atteignables()
       Chiffre l'ecart entre le profil et les seuils qui feraient basculer le
       client dans un autre segment.

PRINCIPE FONDAMENTAL : ce module ne DECIDE jamais
--------------------------------------------------
Il ne reimplemente aucune regle et ne reevalue aucune condition.

    - Le parcours de decision est LU dans la trace deja produite par le moteur
      (`ResultatSegmentation.explications`), jamais recalcule.
    - Les ecarts ne sont pas deduits : pour chaque seuil candidat, on construit
      un profil modifie et on demande AU MOTEUR de le segmenter. Le segment
      annonce est donc toujours celui que le moteur produirait reellement, et
      non une supposition de ce module.

Cette contrainte preserve le principe du moteur unique : il n'existe toujours
qu'un seul endroit ou une segmentation est decidee (core/engine.py). Ce module
ne fait qu'interroger et restituer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Statuts possibles d'une regle dans le parcours de decision.
STATUT_RETENUE = "retenue"
STATUT_REJETEE = "evaluee_rejetee"
STATUT_ELIGIBILITE = "ecartee_eligibilite"
STATUT_NON_EVALUEE = "non_evaluee"

LIBELLES_STATUT = {
    STATUT_RETENUE: "Regle retenue",
    STATUT_REJETEE: "Evaluee, montants insuffisants",
    STATUT_ELIGIBILITE: "Ecartee : critere d'eligibilite (profession ou age)",
    STATUT_NON_EVALUEE: "Non evaluee (regle retenue en amont)",
}


@dataclass
class EtapeRegle:
    """Une regle du marche, avec son sort dans l'evaluation."""
    regle_id: str
    segment: str
    sous_segment: str
    priorite: int
    statut: str
    details: list[str] = field(default_factory=list)

    @property
    def libelle_statut(self) -> str:
        return LIBELLES_STATUT.get(self.statut, self.statut)


@dataclass
class Ecart:
    """Un changement de montant qui ferait basculer le client, VERIFIE par le
    moteur (segment/sous_segment sont ceux que le moteur renvoie reellement)."""
    variable: str          # "MMM" ou "VRD"
    valeur_actuelle: float
    seuil: float
    delta: float           # montant a ajouter pour atteindre le seuil
    segment: str
    sous_segment: str
    regle_id: str


def _index_regles(moteur: Any, marche: str) -> list[dict]:
    """Regles du marche, triees par priorite (meme ordre que le moteur)."""
    contenu = moteur.marches.get(marche)
    if not contenu:
        return []
    return sorted(contenu["regles"], key=lambda r: r.get("priorite", 999))


def parcours_decision(moteur: Any, resultat: Any) -> list[EtapeRegle]:
    """Reconstitue le parcours d'evaluation, regle par regle.

    Le statut de chaque regle est deduit de DEUX faits objectifs, sans aucune
    reevaluation :

      - sa presence (ou non) dans la trace du moteur ;
      - sa priorite comparee a celle de la regle retenue, le moteur s'arretant
        a la premiere regle satisfaite (comportement documente de core/engine).

    D'ou les quatre statuts :
      retenue              : c'est la regle qui a produit la decision ;
      evaluee_rejetee      : tracee, mais conditions monetaires non satisfaites ;
      ecartee_eligibilite  : absente de la trace alors qu'elle precedait la
                             regle retenue -> elle a ete filtree en amont sur
                             un critere d'eligibilite (profession, age,
                             epargnant exclusif) ;
      non_evaluee          : situee apres la regle retenue, donc jamais atteinte.
    """
    marche = getattr(resultat, "marche", "") or ""
    regles = _index_regles(moteur, marche)
    if not regles:
        return []

    explications = getattr(resultat, "explications", []) or []
    regle_retenue = getattr(resultat, "regle_id", None)

    # Lignes de trace regroupees par identifiant de regle.
    traces: dict[str, list[str]] = {}
    for ligne in explications:
        texte = str(ligne).strip()
        if not texte.startswith("["):
            continue
        rid = texte[1:].split("]", 1)[0]
        contenu = texte.split("]", 1)[1].strip() if "]" in texte else texte
        traces.setdefault(rid, []).append(contenu)

    priorite_retenue = None
    if regle_retenue:
        for r in regles:
            if r["id"] == regle_retenue:
                priorite_retenue = r.get("priorite", 999)
                break

    etapes: list[EtapeRegle] = []
    for regle in regles:
        rid = regle["id"]
        priorite = regle.get("priorite", 999)
        if rid == regle_retenue:
            statut = STATUT_RETENUE
        elif rid in traces:
            statut = STATUT_REJETEE
        elif priorite_retenue is not None and priorite > priorite_retenue:
            statut = STATUT_NON_EVALUEE
        else:
            statut = STATUT_ELIGIBILITE
        etapes.append(EtapeRegle(
            regle_id=rid,
            segment=regle.get("segment", ""),
            sous_segment=regle.get("sous_segment", ""),
            priorite=priorite,
            statut=statut,
            details=traces.get(rid, []),
        ))
    return etapes


def ecarts_atteignables(moteur: Any, resultat: Any, limite: int = 4) -> list[Ecart]:
    """Chiffre les changements de montant qui feraient changer de segment.

    Methode, volontairement non deductive :
      1. on releve, dans les regles du marche, les seuils MINIMAUX de MMM et de
         VRD que le profil n'atteint pas encore ;
      2. pour chacun, on construit une COPIE du profil ou la variable est
         portee a ce seuil ;
      3. on demande AU MOTEUR de segmenter ce profil modifie ;
      4. on ne conserve le resultat que si le moteur renvoie effectivement un
         segment ou sous-segment different.

    Le segment annonce est donc toujours celui que le moteur produirait
    reellement : ce module n'infere rien.

    Seules les HAUSSES sont proposees (seuils `min`) : c'est la seule direction
    exploitable commercialement. Les resultats sont tries par effort croissant
    et dedoublonnes par cible atteinte.
    """
    marche = getattr(resultat, "marche", "") or ""
    profil = dict(getattr(resultat, "profil", {}) or {})
    if not marche or not profil:
        return []

    segment_actuel = getattr(resultat, "segment", None)
    sous_actuel = getattr(resultat, "sous_segment", None)

    candidats: list[Ecart] = []
    for regle in _index_regles(moteur, marche):
        for variable in ("MMM", "VRD"):
            bornes = regle["conditions"].get(variable.lower()) or {}
            seuil = bornes.get("min")
            if seuil is None:
                continue
            actuelle = profil.get(variable)
            if actuelle is None:
                continue
            try:
                actuelle = float(actuelle)
            except (TypeError, ValueError):
                continue
            if actuelle >= float(seuil):
                continue  # seuil deja atteint

            profil_modifie = dict(profil)
            profil_modifie[variable] = float(seuil)
            # C'est LE MOTEUR qui tranche, jamais ce module.
            obtenu = moteur.segmenter(profil_modifie)
            if not obtenu.succes:
                continue
            if obtenu.segment == segment_actuel and obtenu.sous_segment == sous_actuel:
                continue  # aucun changement reel

            candidats.append(Ecart(
                variable=variable,
                valeur_actuelle=actuelle,
                seuil=float(seuil),
                delta=float(seuil) - actuelle,
                segment=obtenu.segment,
                sous_segment=obtenu.sous_segment,
                regle_id=obtenu.regle_id,
            ))

    # Effort croissant, une seule proposition par cible (segment/sous-segment).
    candidats.sort(key=lambda e: e.delta)
    retenus: list[Ecart] = []
    cibles_vues: set = set()
    for ecart in candidats:
        cle = (ecart.segment, ecart.sous_segment)
        if cle in cibles_vues:
            continue
        cibles_vues.add(cle)
        retenus.append(ecart)
        if len(retenus) >= limite:
            break
    return retenus
