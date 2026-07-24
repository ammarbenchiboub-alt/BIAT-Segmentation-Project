"""
Analyse de portefeuille : structure de la clientele PBD segmentee.

Paquet d'ANALYSE en lecture seule. Il genere un portefeuille representatif
(simule, aucune donnee reelle BIAT), le fait segmenter par le moteur officiel,
puis en analyse la structure et en tire des recommandations metier.

Il ne modifie ni le moteur, ni les regles, ni aucun resultat de segmentation.
"""
from __future__ import annotations

import pandas as pd

from .analyse import (
    SEGMENTS_MASSE, SEGMENTS_POTENTIEL, SEGMENTS_VALEUR, analyser,
)
from .portefeuille import (
    GRAINE_PORTEFEUILLE, MIX_MARCHE, N_DEFAUT, construire_portefeuille,
    generer_profils, segmenter_portefeuille,
)


def avec_anomalies_ml(portefeuille: pd.DataFrame) -> pd.DataFrame:
    """Ajoute les colonnes ML (ML_Anomalie / ML_Confiance / ML_Niveau) au
    portefeuille, via le module de detection (lecture seule). Import local pour
    ne pas charger la pile scikit-learn si l'appelant n'en a pas besoin."""
    from core.ml_anomaly import analyser_dataframe
    ml = analyser_dataframe(portefeuille)
    return pd.concat([portefeuille, ml], axis=1)


def analyser_portefeuille(n: int = N_DEFAUT, graine: int = GRAINE_PORTEFEUILLE,
                          avec_ml: bool = True) -> dict:
    """Construit le portefeuille representatif, y superpose la detection
    d'anomalies (optionnel), puis en renvoie l'analyse complete."""
    portefeuille = construire_portefeuille(n, graine)
    if avec_ml:
        portefeuille = avec_anomalies_ml(portefeuille)
    return analyser(portefeuille)


__all__ = [
    "construire_portefeuille", "segmenter_portefeuille", "generer_profils",
    "avec_anomalies_ml", "analyser", "analyser_portefeuille",
    "SEGMENTS_VALEUR", "SEGMENTS_POTENTIEL", "SEGMENTS_MASSE",
    "MIX_MARCHE", "GRAINE_PORTEFEUILLE", "N_DEFAUT",
]
