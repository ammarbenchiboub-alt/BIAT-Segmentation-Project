"""
Formatage des montants pour l'affichage.

L'unite de stockage des seuils est le DINAR (DT) dans
config/regles_segmentation.json ; l'unite de LECTURE de la note BIAT est le mD
(millier de dinars), avec 1 mD = 1 000 DT (cf. `meta.unite_seuils`).

Cette conversion etant utilisee a plusieurs endroits de l'interface (chatbot,
referentiel, fiche de decision), elle est definie ICI une seule fois : deux
implementations paralleles finiraient par diverger, comme la configuration
SQLite l'avait fait avant sa factorisation (voir Note 13 du journal).

Formatage uniquement : aucune regle metier, aucun seuil en dur.
"""
from __future__ import annotations

from typing import Any

# Separateur de milliers francais : espace INSECABLE, pour qu'un montant ne
# soit jamais coupe en fin de ligne.
ESPACE_INSECABLE = " "


def en_mD(valeur: Any) -> str:
    """Convertit un montant en DT vers son ecriture en mD (500000 -> '500 mD')."""
    try:
        n = float(valeur)
    except (TypeError, ValueError):
        return str(valeur)
    return f"{n / 1000:g} mD"


def en_dinars(valeur: Any) -> str:
    """Formate un montant en DT avec separateur de milliers (550000 -> '550 000')."""
    try:
        n = float(valeur)
    except (TypeError, ValueError):
        return str(valeur)
    if n == int(n):
        n = int(n)
    return f"{n:,}".replace(",", ESPACE_INSECABLE)
