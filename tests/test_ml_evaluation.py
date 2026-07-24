"""Tests d'evaluation du modele ML (Isolation Forest) — verrouillage des metriques.

Cette suite repond a la remarque du jury « le modele n'est pas evalue ». Elle
mesure le modele LIVRE sur un jeu de reference etiquete et verrouille ses
performances par des seuils prudents (fixes SOUS les valeurs reellement
mesurees, pour rester stables). Une degradation notable du modele ferait donc
echouer la suite.

Elle verifie aussi, structurellement, que l'evaluation reste une ANALYSE :
elle ne reentraine pas le modele et n'importe pas le moteur de segmentation.

Aucune assertion ne porte sur un chiffre qui n'aurait pas ete mesure au
prealable. Tout est deterministe (graines fixees).
"""
from __future__ import annotations

import os
import sys

from _outils import Resultats

import evaluation
from evaluation import construire_jeu_reference, evaluer


def run() -> bool:
    r = Resultats("evaluation du modele ML (Isolation Forest)")

    resultats = evaluer()
    i = resultats["isolation_forest"]
    b = resultats["baseline"]

    # ================================================================== #
    # 1. Jeu de reference etiquete, deterministe
    # ================================================================== #
    jeu = construire_jeu_reference()
    r.egal("jeu de reference : 2000 profils normaux", int((jeu["label"] == 0).sum()), 2000)
    r.egal("  600 anomalies injectees", int((jeu["label"] == 1).sum()), 600)
    r.egal("  5 familles d'anomalies distinctes",
           len(set(jeu.loc[jeu["label"] == 1, "type"])), 5)

    # ================================================================== #
    # 2. Capacite discriminante du modele (independante du seuil)
    # ================================================================== #
    r.verifier(f"ROC-AUC du modele eleve (mesure 0.931, seuil >= 0.85) : {i['roc_auc']:.3f}",
               i["roc_auc"] >= 0.85)
    r.verifier(f"PR-AUC du modele correct (mesure 0.759, seuil >= 0.60) : {i['pr_auc']:.3f}",
               i["pr_auc"] >= 0.60)

    # ================================================================== #
    # 3. Le modele bat la baseline simple (la question du jury)
    # ================================================================== #
    r.verifier(f"le modele classe mieux que la baseline "
               f"(AUC {i['roc_auc']:.3f} vs {b['roc_auc']:.3f})",
               i["roc_auc"] >= b["roc_auc"] + 0.05)

    # ================================================================== #
    # 4. Controle des fausses alertes : le point decisif
    # ================================================================== #
    # C'est l'interpretation de contamination=0.06 ET l'avantage concret du
    # modele : il ne noie pas le conseiller sous les fausses alertes.
    r.verifier(f"fausses alertes du modele ~ contamination 6% "
               f"(mesure 5.6%, tolerance 3-9%) : {i['fausses_alertes_normaux']:.1%}",
               0.03 <= i["fausses_alertes_normaux"] <= 0.09)
    r.verifier(f"la baseline noie de fausses alertes (mesure 27.6%, seuil > 15%) : "
               f"{b['fausses_alertes_normaux']:.1%}",
               b["fausses_alertes_normaux"] > 0.15)
    r.verifier("le modele produit au moins 2x moins de fausses alertes que la baseline",
               i["fausses_alertes_normaux"] * 2 < b["fausses_alertes_normaux"])

    # ================================================================== #
    # 5. Coherence par type d'anomalie
    # ================================================================== #
    r.verifier("montants extremes detectes par le modele (mesure 100%)",
               resultats["rappel_par_type_if"]["montant_extreme"] >= 0.95)
    # Faiblesse categorielle DOCUMENTEE : on verifie qu'elle est bien reelle
    # (rappel faible), pour que le rapport ne survende pas le modele.
    r.verifier("faiblesse categorielle reelle et documentee (ENR nationalite < 50%)",
               resultats["rappel_par_type_if"]["ENR_nationalite_tunisienne"] < 0.50)

    # ================================================================== #
    # 6. Courbe operationnelle : le seuil est un compromis explicite
    # ================================================================== #
    courbe = {round(p["budget_fausses_alertes"], 2): p["rappel"]
              for p in resultats["courbe_operationnelle"]}
    r.verifier("plus de budget de fausses alertes -> plus de rappel (monotone)",
               courbe[0.15] > courbe[0.02])
    r.verifier("  le reglage a 6% offre un rappel intermediaire raisonnable",
               0.30 <= courbe[0.06] <= 0.90)

    # ================================================================== #
    # 7. Determinisme (reproductibilite exigee pour un jury)
    # ================================================================== #
    resultats2 = evaluer()
    r.egal("evaluation deterministe : ROC-AUC identique entre deux executions",
           resultats2["isolation_forest"]["roc_auc"], i["roc_auc"])
    r.egal("  F1 identique", resultats2["isolation_forest"]["f1"], i["f1"])
    r.egal("  fausses alertes identiques",
           resultats2["isolation_forest"]["fausses_alertes_normaux"],
           i["fausses_alertes_normaux"])

    # ================================================================== #
    # 8. Garanties structurelles : l'evaluation ne fait qu'ANALYSER
    # ================================================================== #
    dossier = os.path.dirname(evaluation.__file__)
    sources = ""
    for nom in ("jeu_reference.py", "mesures.py", "rapport.py", "__init__.py"):
        with open(os.path.join(dossier, nom), encoding="utf-8") as f:
            sources += f.read()
    r.verifier("l'evaluation ne reentraine pas le modele (pas d'appel .entrainer( )",
               ".entrainer(" not in sources)
    r.verifier("l'evaluation ne sauvegarde jamais le modele (pas d'appel .sauvegarder( )",
               ".sauvegarder(" not in sources)
    r.verifier("l'evaluation n'importe pas le moteur de segmentation",
               "core.engine" not in sources and "from core import" not in sources)

    # Le fichier modele n'est pas altere par une evaluation.
    from core.ml_anomaly import CHEMIN_MODELE
    if os.path.exists(CHEMIN_MODELE):
        mtime_avant = os.path.getmtime(CHEMIN_MODELE)
        evaluer()
        r.egal("le fichier modele (.joblib) n'est pas reecrit par l'evaluation",
               os.path.getmtime(CHEMIN_MODELE), mtime_avant)

    print(f"\n  Synthese : IF ROC-AUC={i['roc_auc']:.3f} (baseline {b['roc_auc']:.3f}), "
          f"fausses alertes {i['fausses_alertes_normaux']:.1%} (baseline "
          f"{b['fausses_alertes_normaux']:.1%}).")

    return r.bilan()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
