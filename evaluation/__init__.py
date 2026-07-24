"""
Evaluation du module de detection d'anomalies (Isolation Forest).

Paquet d'ANALYSE, strictement en lecture : il charge le modele livre, le note
sur un jeu de reference etiquete et le compare a une baseline. Il ne reentraine
jamais le modele, ne le sauvegarde jamais, et n'importe pas le moteur de
segmentation. Sa presence ne peut donc modifier ni le modele, ni les regles,
ni aucun resultat de segmentation.
"""
from .jeu_reference import (
    GRAINE_EVALUATION, TYPES_ANOMALIES, construire_jeu_reference,
)
from .mesures import evaluer

__all__ = ["construire_jeu_reference", "evaluer", "GRAINE_EVALUATION", "TYPES_ANOMALIES"]
