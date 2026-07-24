"""Tests de l'explicabilite (P1) et de la fiche de decision (P2).

Propriete CENTRALE verifiee ici : ces modules n'inventent aucune decision.

  - le parcours d'evaluation est LU dans la trace du moteur ;
  - chaque ecart annonce ("il manque X DT pour atteindre Y") est RE-VERIFIE
    independamment : on reconstruit le profil modifie et l'on demande au moteur
    de le segmenter. Si le moteur ne renvoyait pas le segment annonce, le test
    echouerait.

C'est la garantie que le principe du moteur unique reste intact : aucun segment
n'est produit ailleurs que dans core/engine.py.
"""
from __future__ import annotations

import sys

from _outils import Resultats

from core import MoteurSegmentation
from explicabilite import (
    STATUT_ELIGIBILITE, STATUT_NON_EVALUEE, STATUT_REJETEE, STATUT_RETENUE,
    ecarts_atteignables, parcours_decision,
)
from presentation import generer_fiche_html

PROFILS = [
    {"Marche": "PART", "Profession": "Autre", "Age": 45, "MMM": 300.0, "VRD": 1000.0,
     "Nationalite": "Tunisienne", "Residence": "Oui"},
    {"Marche": "PART", "Profession": "Ingenieurs", "Age": 45, "MMM": 5000.0, "VRD": 550000.0,
     "Nationalite": "Tunisienne", "Residence": "Oui"},
    {"Marche": "PRO", "Profession": "Commercant", "Age": 40, "MMM": 90.0, "VRD": 3.0,
     "Nationalite": "Tunisienne", "Residence": "Oui"},
    {"Marche": "TRE", "Profession": "Autre", "Age": 40, "MMM": 0.0, "VRD": 30000.0,
     "Nationalite": "Tunisienne", "Residence": "Non"},
    {"Marche": "ENR", "Profession": "Autre", "Age": 30, "MMM": 0.0, "VRD": 5000.0,
     "Nationalite": "Autre", "Residence": "Non"},
]


def run() -> bool:
    r = Resultats("explicabilite & fiche de decision")
    moteur = MoteurSegmentation()

    # ================================================================== #
    # 1. Parcours de decision
    # ================================================================== #
    profil = PROFILS[0]
    res = moteur.segmenter(profil)
    etapes = parcours_decision(moteur, res)

    nb_regles_marche = len(moteur.marches["PART"]["regles"])
    r.egal("le parcours couvre TOUTES les regles du marche", len(etapes), nb_regles_marche)
    r.egal("  une seule regle est marquee 'retenue'",
           sum(1 for e in etapes if e.statut == STATUT_RETENUE), 1)
    retenue = next(e for e in etapes if e.statut == STATUT_RETENUE)
    r.egal("  et c'est bien celle du moteur", retenue.regle_id, res.regle_id)
    r.egal("  avec le segment du moteur", retenue.segment, res.segment)

    r.verifier("les etapes sont triees par priorite croissante",
               [e.priorite for e in etapes] == sorted(e.priorite for e in etapes))
    r.verifier("tous les statuts sont connus",
               all(e.statut in (STATUT_RETENUE, STATUT_REJETEE, STATUT_ELIGIBILITE,
                                STATUT_NON_EVALUEE) for e in etapes))
    r.verifier("chaque etape porte un libelle lisible",
               all(e.libelle_statut and e.libelle_statut != e.statut for e in etapes))

    # Les regles evaluees-rejetees doivent porter la trace du moteur.
    rejetees = [e for e in etapes if e.statut == STATUT_REJETEE]
    r.verifier("les regles rejetees citent la trace du moteur",
               all(e.details for e in rejetees) if rejetees else True)

    # Aucune regle posterieure a la regle retenue ne peut avoir ete evaluee.
    posterieures = [e for e in etapes if e.priorite > retenue.priorite]
    r.verifier("aucune regle posterieure a la regle retenue n'est evaluee",
               all(e.statut == STATUT_NON_EVALUEE for e in posterieures))

    # ================================================================== #
    # 2. Ecarts : chaque annonce est RE-VERIFIEE par le moteur
    # ================================================================== #
    total_ecarts = 0
    for p in PROFILS:
        resultat = moteur.segmenter(p)
        ecarts = ecarts_atteignables(moteur, resultat)
        total_ecarts += len(ecarts)
        for ec in ecarts:
            # Reconstruction independante du profil modifie.
            modifie = dict(p)
            modifie[ec.variable] = ec.seuil
            obtenu = moteur.segmenter(modifie)
            r.egal(f"[{p['Marche']}] +{ec.delta:g} {ec.variable} -> segment annonce verifie",
                   obtenu.segment, ec.segment)
            r.egal(f"[{p['Marche']}]   sous-segment verifie",
                   obtenu.sous_segment, ec.sous_segment)
            r.egal(f"[{p['Marche']}]   regle verifiee", obtenu.regle_id, ec.regle_id)
            # Coherence arithmetique de l'ecart annonce.
            r.verifier(f"[{p['Marche']}]   ecart = seuil - valeur actuelle",
                       abs((ec.seuil - ec.valeur_actuelle) - ec.delta) < 1e-6)
            # Un ecart ne doit jamais proposer le segment deja obtenu.
            r.verifier(f"[{p['Marche']}]   la cible differe du segment actuel",
                       (ec.segment, ec.sous_segment) != (resultat.segment, resultat.sous_segment))
    r.verifier(f"des ecarts exploitables sont produits ({total_ecarts} au total)",
               total_ecarts > 0)

    # Seules des HAUSSES sont proposees (seule direction actionnable).
    for p in PROFILS:
        for ec in ecarts_atteignables(moteur, moteur.segmenter(p)):
            r.verifier(f"[{p['Marche']}] l'ecart est une hausse", ec.delta > 0)

    # ================================================================== #
    # 3. Robustesse
    # ================================================================== #
    hors_perimetre = moteur.segmenter({"Marche": "TPME", "Age": 40, "MMM": 0, "VRD": 0})
    try:
        r.egal("marche non gere -> parcours vide, sans exception",
               parcours_decision(moteur, hors_perimetre), [])
        r.egal("marche non gere -> aucun ecart, sans exception",
               ecarts_atteignables(moteur, hors_perimetre), [])
    except Exception as exc:  # noqa: BLE001
        r.verifier("marche non gere traite sans exception", False, repr(exc))

    # ================================================================== #
    # 4. Fiche de decision (P2)
    # ================================================================== #
    res_riche = moteur.segmenter(PROFILS[1])
    html_fiche = generer_fiche_html(
        res_riche,
        utilisateur={"identifiant": "admin1", "nom": "Administrateur 1", "role": "admin"},
        version_regles="abc123def456",
        etapes=parcours_decision(moteur, res_riche),
        ecarts=ecarts_atteignables(moteur, res_riche),
    )
    r.verifier("la fiche est un document HTML complet",
               html_fiche.startswith("<!DOCTYPE html>") and html_fiche.rstrip().endswith("</html>"))
    r.verifier("  elle porte le segment decide par le moteur", res_riche.segment in html_fiche)
    r.verifier("  et le sous-segment", (res_riche.sous_segment or "") in html_fiche)
    r.verifier("  et la regle appliquee", (res_riche.regle_id or "") in html_fiche)
    r.verifier("  et l'EMPREINTE de la version des regles (rejouabilite)",
               "abc123def456" in html_fiche)
    r.verifier("  et l'agent auteur de la decision (tracabilite)",
               "Administrateur 1" in html_fiche and "admin1" in html_fiche)
    r.verifier("  et les montants du profil formates",
               "550" in html_fiche and "DT" in html_fiche)
    r.verifier("  elle cite la note BIAT 2023-06", "2023-06" in html_fiche)

    # Document AUTONOME : aucune ressource externe (pas de reseau a l'ouverture).
    for marqueur in ("http://", "https://", "<script", "<img"):
        r.verifier(f"  document autonome : aucun '{marqueur}'", marqueur not in html_fiche)

    # Echappement HTML (defense en profondeur sur une donnee saisie).
    res_injection = moteur.segmenter({**PROFILS[0], "Profession": "<script>alert(1)</script>"})
    html_injection = generer_fiche_html(res_injection, version_regles="x")
    r.verifier("  les donnees de profil sont echappees",
               "<script>alert(1)</script>" not in html_injection
               and "&lt;script&gt;" in html_injection)

    # Cas non segmente : la fiche reste produite et signale l'echec.
    html_ko = generer_fiche_html(hors_perimetre, version_regles="x")
    r.verifier("  une decision sans segment produit tout de meme une fiche",
               "Non segmente" in html_ko)

    return r.bilan()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
