"""
Explicabilite des decisions de segmentation.

Repond a « pourquoi ce segment ? » et « que faudrait-il pour en changer ? »,
sans jamais decider : le parcours est LU dans la trace du moteur, et chaque
ecart chiffre est VERIFIE en redemandant une segmentation au moteur.

Ce paquet est independant de l'interface (aucun import Streamlit) et ne
contient aucune regle metier : il lit `core` sans jamais le modifier.
"""
from .analyse import (
    STATUT_ELIGIBILITE, STATUT_NON_EVALUEE, STATUT_REJETEE, STATUT_RETENUE,
    Ecart, EtapeRegle, ecarts_atteignables, parcours_decision,
)

__all__ = [
    "parcours_decision", "ecarts_atteignables", "EtapeRegle", "Ecart",
    "STATUT_RETENUE", "STATUT_REJETEE", "STATUT_ELIGIBILITE", "STATUT_NON_EVALUEE",
]
