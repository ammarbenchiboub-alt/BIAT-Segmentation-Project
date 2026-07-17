"""
Chargement centralise des regles metier.

La SEULE source de regles est config/regles_segmentation.json, lui-meme
issu exclusivement de la Note BIAT 2023-06. Aucun autre fichier ne doit
contenir de logique de segmentation.
"""
from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache

# Chemin absolu vers le fichier de regles, robuste quel que soit le cwd.
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHEMIN_REGLES = os.path.join(_BASE_DIR, "config", "regles_segmentation.json")


def empreinte_regles(chemin: str | None = None) -> str:
    """Empreinte SHA-256 (16 hex) du fichier de regles ACTUEL.

    Source unique d'identification d'une version des regles. Utilisee par :
      - audit/journal.py : tracer avec quelle version des seuils une decision
        a ete prise (voir _hash_regles_actives) ;
      - app.py : clef de cache du moteur (@st.cache_resource). Des que le
        fichier de regles change, l'empreinte change, donc Streamlit
        reconstruit automatiquement le moteur -- et UNIQUEMENT dans ce cas.

    Volontairement basee sur le CONTENU et non sur la date de modification :
    un mtime peut etre identique pour deux ecritures dans la meme seconde
    (le cache resterait alors sur des regles perimees), et peut changer sans
    que le contenu change (reconstruction inutile du moteur).
    """
    chemin = chemin or CHEMIN_REGLES
    with open(chemin, "rb") as fichier:
        return hashlib.sha256(fichier.read()).hexdigest()[:16]


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
