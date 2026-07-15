"""
Segmentation en masse (import CSV).

IMPORTANT : ce module n'implemente AUCUNE logique de segmentation.
Il se contente d'appeler le moteur unique (core.engine) ligne par ligne.
"""
from __future__ import annotations

from core import MoteurSegmentation
from validation import valider_dataframe


def segmenter_dataframe(df, moteur: MoteurSegmentation | None = None):
    """Valide puis segmente un DataFrame via le moteur unique.

    Renvoie (df_resultats, df_invalides).
    """
    import pandas as pd

    moteur = moteur or MoteurSegmentation()
    df_valide, df_invalide = valider_dataframe(df)

    resultats = []
    for _, profil in df_valide.iterrows():
        r = moteur.segmenter(profil.to_dict())
        ligne = profil.to_dict()
        ligne["Segment"] = r.segment or "-"
        ligne["Sous_segment"] = r.sous_segment or "-"
        ligne["Regle"] = r.regle_id or "-"
        ligne["Statut"] = "Segmente" if r.succes else "Non segmente"
        resultats.append(ligne)

    return pd.DataFrame(resultats), df_invalide
