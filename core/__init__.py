"""Package core : moteur unique de segmentation BIAT."""
from .engine import MoteurSegmentation, ResultatSegmentation, segmenter
from .rules_loader import charger_regles, CHEMIN_REGLES

__all__ = [
    "MoteurSegmentation",
    "ResultatSegmentation",
    "segmenter",
    "charger_regles",
    "CHEMIN_REGLES",
]
