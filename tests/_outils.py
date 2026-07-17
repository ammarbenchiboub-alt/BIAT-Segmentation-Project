"""Outils partages par les tests.

Objectif principal : ISOLATION. Aucun test ne doit ecrire dans le vrai
journal d'audit, le vrai fichier de comptes ou les vraies regles. Chaque test
redirige les modules concernes vers un dossier temporaire, puis restaure les
chemins d'origine -- de sorte que lancer les tests ne laisse aucune trace dans
l'application reelle.
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Resultats:
    """Compteur de tests, avec la meme sortie lisible que tests/test_moteur.py."""

    def __init__(self, titre: str):
        self.titre = titre
        self.ok = 0
        self.total = 0
        self.echecs: list[str] = []

    def verifier(self, libelle: str, condition: bool, detail: str = "") -> None:
        self.total += 1
        if condition:
            self.ok += 1
            print(f"[OK ] {libelle}")
        else:
            self.echecs.append(libelle)
            print(f"[ECHEC] {libelle}")
            if detail:
                print(f"        {detail}")

    def egal(self, libelle: str, obtenu, attendu) -> None:
        self.verifier(libelle, obtenu == attendu, f"attendu: {attendu!r}  obtenu: {obtenu!r}")

    def bilan(self) -> bool:
        print(f"\n{self.ok}/{self.total} cas reussis - {self.titre}")
        return self.ok == self.total


def dossier_temporaire() -> str:
    return tempfile.mkdtemp(prefix="biat_test_")


class ModulesRediriges:
    """Redirige des attributs de module (chemins de fichiers) puis les restaure.

    Utilisation :
        with ModulesRediriges((journal, "CHEMIN_JOURNAL", "/tmp/x.sqlite3")):
            ...
    """

    def __init__(self, *redirections):
        self.redirections = redirections
        self.anciennes: list[tuple] = []

    def __enter__(self):
        for module, attribut, valeur in self.redirections:
            self.anciennes.append((module, attribut, getattr(module, attribut)))
            setattr(module, attribut, valeur)
        return self

    def __exit__(self, *_):
        for module, attribut, valeur in self.anciennes:
            setattr(module, attribut, valeur)
        return False
