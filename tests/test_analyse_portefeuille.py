"""Tests de l'analyse de portefeuille (point 4 du jury).

Verrouille les proprietes STRUCTURELLES de l'analyse (deterministe, credible,
lecture seule), sans figer chaque decimale : les seuils sont larges et fondes
sur les valeurs mesurees, pour rester stables.

Verifie surtout que l'analyse :
  - segmente via le MOTEUR OFFICIEL (les segments produits appartiennent bien a
    la nomenclature de la note) ;
  - produit une pyramide credible (masse > valeur) et une concentration des
    avoirs coherente (Gini > 0) ;
  - genere des constats et des recommandations non vides, chiffres ;
  - ne modifie ni le moteur, ni les regles, ni aucun resultat.
"""
from __future__ import annotations

import os
import sys

from _outils import Resultats

import analyse_portefeuille as ap
from analyse_portefeuille import (
    analyser, avec_anomalies_ml, construire_portefeuille, MIX_MARCHE,
)
from core import MoteurSegmentation

_SEGMENTS_NOTE = {
    "Haut de Gamme", "Classe Moyenne", "Grand Public", "Les Jeunes",
    "Premium", "Potentiel moyen", "Faible potentiel",
}


def run() -> bool:
    r = Resultats("analyse de portefeuille (structure & recommandations)")

    portefeuille = construire_portefeuille()

    # ================================================================== #
    # 1. Portefeuille : taille, mix, segments issus du moteur
    # ================================================================== #
    r.verifier("le portefeuille compte plusieurs milliers de clients",
               len(portefeuille) >= 5000)
    r.verifier("le mix de marche respecte l'hypothese (PART majoritaire)",
               (portefeuille["Marche"] == "PART").mean() > 0.5)
    r.egal("les 4 marches sont representes",
           sorted(portefeuille["Marche"].unique()), ["ENR", "PART", "PRO", "TRE"])

    segments_produits = set(portefeuille.loc[portefeuille["Segment"] != "-", "Segment"])
    r.verifier("tous les segments produits appartiennent a la nomenclature de la note",
               segments_produits.issubset(_SEGMENTS_NOTE), str(segments_produits))

    # Les segments viennent BIEN du moteur (verification independante d'un profil).
    ligne = portefeuille.iloc[0]
    attendu = MoteurSegmentation().segmenter({
        "Marche": ligne["Marche"], "Profession": ligne["Profession"], "Age": int(ligne["Age"]),
        "MMM": float(ligne["MMM"]), "VRD": float(ligne["VRD"]),
        "Nationalite": ligne["Nationalite"], "Residence": ligne["Residence"],
    })
    r.egal("le segment stocke correspond au moteur", ligne["Segment"], attendu.segment or "-")

    # ================================================================== #
    # 2. Analyse : pyramide credible + concentration
    # ================================================================== #
    a = analyser(avec_anomalies_ml(portefeuille))

    somme = sum(v for s, v in a["repartition_segment"].items() if s != "-")
    r.verifier(f"la repartition somme a ~100 % (obtenu {somme:.1f})", 99.0 <= somme <= 101.0)

    r.verifier(f"pyramide credible : masse ({a['part_masse']} %) > valeur ({a['part_valeur']} %)",
               a["part_masse"] > a["part_valeur"])
    r.verifier(f"le Haut de Gamme reste une minorite (part valeur {a['part_valeur']} % < 25 %)",
               a["part_valeur"] < 25)

    r.verifier(f"concentration des avoirs reelle : top 10 % > proportionnel "
               f"(obtenu {a['concentration_top10']} %)",
               a["concentration_top10"] > 15)
    r.verifier(f"indice de Gini dans ]0,1[ (obtenu {a['gini_avoirs']})",
               0 < a["gini_avoirs"] < 1)
    r.verifier("top 20 % >= top 10 % (coherence)",
               a["concentration_top20"] >= a["concentration_top10"])

    # ================================================================== #
    # 3. Croisement marche x segment
    # ================================================================== #
    r.egal("le croisement couvre les 4 marches",
           sorted(a["croise_marche_segment"].keys()), ["ENR", "PART", "PRO", "TRE"])
    for marche, ligne_ct in a["croise_marche_segment"].items():
        total = sum(ligne_ct.values())
        r.verifier(f"  {marche} : les parts somment a ~100 % ({total:.0f})",
                   99.0 <= total <= 101.0)

    # ================================================================== #
    # 4. Constats et recommandations : non vides et chiffres
    # ================================================================== #
    r.verifier("des constats sont produits", len(a["constats"]) >= 3)
    r.verifier("des recommandations sont produites", len(a["recommandations"]) >= 1)
    r.verifier("  chaque recommandation contient au moins un chiffre",
               all(any(c.isdigit() for c in reco) for reco in a["recommandations"]))
    r.verifier("  le taux d'anomalies ML est calcule (overlay qualite donnees)",
               a["taux_anomalies"] is not None)

    # ================================================================== #
    # 5. Determinisme (reproductibilite exigee pour un jury)
    # ================================================================== #
    a2 = analyser(construire_portefeuille())
    r.egal("analyse deterministe : repartition identique",
           a2["repartition_segment"], analyser(construire_portefeuille())["repartition_segment"])
    r.egal("  concentration identique", a2["concentration_top10"], a["concentration_top10"])

    # ================================================================== #
    # 6. Garanties structurelles : analyse en lecture seule
    # ================================================================== #
    dossier = os.path.dirname(ap.__file__)
    sources = ""
    for nom in ("portefeuille.py", "analyse.py", "rapport.py", "__init__.py"):
        with open(os.path.join(dossier, nom), encoding="utf-8") as f:
            sources += f.read()
    r.verifier("l'analyse ne modifie pas les regles (pas d'ecriture du JSON)",
               "regles_segmentation.json" not in sources or "open(" not in sources)
    r.verifier("l'analyse ne reentraine pas le modele ML",
               ".entrainer(" not in sources and "reentrainer" not in sources)

    print(f"\n  Synthese : {a['n_clients']} clients, valeur {a['part_valeur']} %, "
          f"masse {a['part_masse']} %, top 10 % = {a['concentration_top10']} % des avoirs "
          f"(Gini {a['gini_avoirs']}), {len(a['recommandations'])} recommandations.")

    return r.bilan()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
