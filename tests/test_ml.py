"""Tests du module Machine Learning (detection d'anomalies).

Ce module est COMPLEMENTAIRE : il ne doit jamais influencer la segmentation.
Les tests verifient donc autant son INDEPENDANCE que son exactitude.

Non-regressions de defauts constates lors de la revue d'architecture :

  1. analyser_dataframe() appelait le modele LIGNE PAR LIGNE : 5 000 lignes
     prenaient 73 s, cout repaye a chaque interaction Streamlit. Vectorise, le
     lot ne coute plus qu'un appel -- a resultats strictement identiques, ce
     que ce fichier verifie explicitement plutot que de le supposer.
  2. Le modele livre (anomaly_pipeline.joblib) avait ete entraine avec
     scikit-learn 1.7.2 alors que requirements.txt figeait la 1.9.0 : son
     rechargement declenchait InconsistentVersionWarning ("might lead to [...]
     invalid results"). Un test verrouille desormais l'accord entre le modele
     livre et la version figee.
"""
from __future__ import annotations

import sys
import warnings

import numpy as np
import pandas as pd

from _outils import Resultats

import core.ml_anomaly as ml_anomaly
from core.ml_anomaly import DetecteurAnomalies, analyser_anomalie, analyser_dataframe


def _profils_varies(n: int) -> list[dict]:
    """Profils volontairement heterogenes : marches inconnus, champs vides et
    professions hors liste inclus, pour eprouver aussi les cas limites."""
    rng = np.random.default_rng(7)
    return [
        {
            "Marche": str(rng.choice(["PART", "PRO", "TRE", "ENR", "INCONNU", ""])),
            "Profession": str(rng.choice(
                ["Autre", "Etudiant", "Commercant", "Magistrats", "Ingenieurs", "", "Inexistante"]
            )),
            "Age": int(rng.integers(0, 100)),
            "MMM": float(rng.integers(0, 200_000)),
            "VRD": float(rng.integers(0, 800_000)),
            "Nationalite": str(rng.choice(["Tunisienne", "Autre", ""])),
            "Residence": str(rng.choice(["Oui", "Non", ""])),
        }
        for _ in range(n)
    ]


def run() -> bool:
    r = Resultats("module Machine Learning")

    # ================================================================== #
    # 1. Le modele livre s'accorde avec la version de scikit-learn figee
    # ================================================================== #
    with warnings.catch_warnings(record=True) as captures:
        warnings.simplefilter("always")
        ml_anomaly._DETECTEUR = None
        detecteur = ml_anomaly._detecteur()
    incoherences = [w for w in captures if "InconsistentVersionWarning" in type(w.message).__name__]
    r.egal("le modele livre se recharge sans avertissement de version scikit-learn",
           [str(w.message)[:60] for w in incoherences], [])
    r.verifier("  le modele est charge", detecteur.pipeline is not None)

    # ================================================================== #
    # 2. Vectorisation : resultats STRICTEMENT identiques au ligne-a-ligne
    # ================================================================== #
    profils = _profils_varies(500)
    df = pd.DataFrame(profils)

    # Reference : l'ancienne logique, une ligne a la fois.
    reference = [detecteur.analyser(ligne.to_dict()) for _, ligne in df.iterrows()]
    obtenu = detecteur.analyser_dataframe(df)

    r.egal("vectorise vs ligne-a-ligne : ML_Anomalie identique",
           list(obtenu["ML_Anomalie"]), [x["anomalie"] for x in reference])
    r.egal("  ML_Confiance identique",
           list(obtenu["ML_Confiance"]), [x["score_confiance"] for x in reference])
    r.egal("  ML_Niveau identique",
           list(obtenu["ML_Niveau"]), [x["niveau"] for x in reference])

    # Les scores bruts doivent coincider au bit pres : c'est la propriete qui
    # autorise la vectorisation (Isolation Forest note chaque ligne
    # independamment des autres lignes du lot).
    unitaires = np.array([detecteur._scores_bruts([p])[0] for p in profils[:200]])
    par_lot = detecteur._scores_bruts(profils[:200])
    r.verifier("  scores bruts identiques au bit pres (ecart max = 0)",
               np.array_equal(unitaires, par_lot),
               f"ecart max : {np.abs(unitaires - par_lot).max()}")

    # ================================================================== #
    # 3. Cas limites
    # ================================================================== #
    vide = detecteur.analyser_dataframe(pd.DataFrame(columns=["Marche", "Age"]))
    r.egal("DataFrame vide -> resultat vide, sans exception", len(vide), 0)
    r.egal("  colonnes attendues presentes",
           list(vide.columns), ["ML_Anomalie", "ML_Confiance", "ML_Niveau"])

    # Index non trivial : les colonnes ML doivent rester alignees sur l'index
    # d'origine, sinon la concatenation dans app.py melangerait les lignes.
    df_index = pd.DataFrame(_profils_varies(10), index=[100, 3, 57, 8, 9, 1, 2, 44, 6, 7])
    res_index = detecteur.analyser_dataframe(df_index)
    r.egal("index d'origine preserve (alignement de la concatenation)",
           list(res_index.index), list(df_index.index))

    profil_minimal = {"Marche": "PART"}
    sortie = analyser_anomalie(profil_minimal)
    r.verifier("profil minimal (champs manquants) -> pas d'exception",
               "niveau" in sortie)
    r.verifier("  score de confiance dans [0, 100]",
               0 <= sortie["score_confiance"] <= 100)

    sortie_extreme = analyser_anomalie(
        {"Marche": "PART", "Age": 0, "MMM": 0, "VRD": 0, "Profession": "", "Nationalite": "", "Residence": ""}
    )
    r.verifier("profil entierement vide/nul -> pas d'exception",
               sortie_extreme["niveau"] in ("Normal", "Atypique", "Incoherent"))

    # ================================================================== #
    # 4. Independance vis-a-vis du moteur de segmentation
    # ================================================================== #
    interdits = {"segment", "sous_segment", "regle_id", "Segment", "Sous_segment"}
    r.egal("l'analyse ML ne renvoie JAMAIS de segment",
           sorted(interdits & set(sortie.keys())), [])
    r.egal("  ni de sous-segment dans l'analyse en masse",
           sorted(interdits & set(obtenu.columns)), [])

    source = open(ml_anomaly.__file__, encoding="utf-8").read()
    r.verifier("core/ml_anomaly.py n'importe jamais core.engine",
               "from .engine" not in source and "import engine" not in source
               and "core.engine" not in source.split('"""')[-1])

    # Le sens inverse est la garantie structurelle la plus importante : le
    # moteur ne doit dependre d'aucun module ML.
    source_moteur = open(
        ml_anomaly.__file__.replace("ml_anomaly.py", "engine.py"), encoding="utf-8"
    ).read()
    r.verifier("core/engine.py n'importe JAMAIS ml_anomaly (garantie structurelle)",
               "ml_anomaly" not in source_moteur)
    r.verifier("  ni scikit-learn / numpy",
               "sklearn" not in source_moteur and "numpy" not in source_moteur)

    # Importer le paquet `core` ne doit pas tirer scikit-learn : le moteur doit
    # rester utilisable (et testable) sans la pile ML.
    source_init = open(
        ml_anomaly.__file__.replace("ml_anomaly.py", "__init__.py"), encoding="utf-8"
    ).read()
    r.verifier("`import core` ne charge pas le module ML (paquet leger)",
               "ml_anomaly" not in source_init)

    # ================================================================== #
    # 5. Determinisme
    # ================================================================== #
    a = analyser_anomalie(profils[0])
    b = analyser_anomalie(profils[0])
    r.egal("meme profil -> meme score (deterministe)",
           a["score_confiance"], b["score_confiance"])

    return r.bilan()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
