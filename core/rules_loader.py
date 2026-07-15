"""
Chargement centralise des regles metier.

La SEULE source de regles est config/regles_segmentation.json, lui-meme
issu exclusivement de la Note BIAT 2023-06. Aucun autre fichier ne doit
contenir de logique de segmentation.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

# Chemin absolu vers le fichier de regles, robuste quel que soit le cwd.
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHEMIN_REGLES = os.path.join(_BASE_DIR, "config", "regles_segmentation.json")


def charger_regles(chemin: str | None = None) -> dict:
    """Charge et renvoie le dictionnaire de regles depuis le JSON.

    Parametres
    ----------
    chemin : str, optionnel
        Chemin alternatif (utilise par la page Parametrage / les tests).
    """
    chemin = chemin or CHEMIN_REGLES
    with open(chemin, "r", encoding="utf-8") as fichier:
        return json.load(fichier)


@lru_cache(maxsize=1)
def charger_regles_cache() -> dict:
    """Version mise en cache (lecture unique) pour l'execution normale."""
    return charger_regles()
