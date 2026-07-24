"""Socle technique partage.

Contient uniquement des utilitaires TECHNIQUES, sans aucune connaissance du
metier bancaire : ce paquet ne doit jamais contenir de regle de segmentation,
de seuil, ni de notion de segment. Il est importable par n'importe quelle
couche sans creer de dependance vers le metier.
"""
from .base_sqlite import connexion_durable
from .formatage import en_dinars, en_mD

__all__ = ["connexion_durable", "en_mD", "en_dinars"]
