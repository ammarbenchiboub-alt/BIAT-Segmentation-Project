"""
Referentiel BIAT : restitution consultable des regles de segmentation.

Met en forme, pour lecture, le contenu de config/regles_segmentation.json
(seuils, professions, metadonnees, points de vigilance). Aucune valeur n'est
saisie en dur : tout est lu depuis la source unique via le moteur, si bien
qu'un changement valide en Parametrage se reflete immediatement ici.

Aucun import Streamlit : le module est testable sans interface.
"""
from .tables import (
    GLOSSAIRE, compter_regles, listes_professions, marches, metadonnees,
    points_de_vigilance, table_regles,
)

__all__ = [
    "table_regles", "marches", "listes_professions", "metadonnees",
    "points_de_vigilance", "compter_regles", "GLOSSAIRE",
]
