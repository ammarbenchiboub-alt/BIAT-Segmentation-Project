"""Tests de l'import de fichiers (CSV / Excel multi-feuilles).

Non-regression d'un defaut signale par l'utilisateur en usage reel : l'import
du fichier de test livre (Jeu_de_test_segmentation_BIAT.xlsx) donnait
0 ligne segmentee et 18 lignes invalides ("colonne Marche absente").

Cause : le classeur comporte trois feuilles [Notice, Test_Import, Listes] et
les donnees sont dans Test_Import, mais pandas.read_excel ne lit par defaut que
la PREMIERE feuille (Notice, du texte). Le modele genere par l'application, lui,
place la feuille de donnees en premier, d'ou l'asymetrie : le modele
fonctionnait, le fichier de test non.

Correction : selectionner_feuille() retient la feuille contenant les colonnes
obligatoires, quel que soit son rang.

Ces tests utilisent le VRAI fichier livre, pas un fichier reconstruit : c'est
la seule facon de garantir que le scenario exact de l'utilisateur fonctionne.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

from _outils import Resultats

from core import MoteurSegmentation
from segmentation import segmenter_dataframe
from validation import COLONNES_OBLIGATOIRES, selectionner_feuille

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FICHIER_TEST = os.path.join(_RACINE, "Jeu_de_test_segmentation_BIAT.xlsx")


def run() -> bool:
    r = Resultats("import de fichiers (CSV / Excel multi-feuilles)")

    # ================================================================== #
    # 1. selectionner_feuille : choix de la bonne feuille
    # ================================================================== #
    feuilles = {
        "Notice": pd.DataFrame({"FICHIER DE TEST": ["ligne de texte"]}),
        "Test_Import": pd.DataFrame(
            {c: [] for c in ["Marche", "Profession", "Age", "MMM", "VRD"]}
        ),
        "Listes": pd.DataFrame({"Marche": [], "Residence": []}),
    }
    choisie = selectionner_feuille(feuilles)
    r.verifier("la feuille de DONNEES est retenue, pas la notice en tete",
               set(COLONNES_OBLIGATOIRES).issubset(set(choisie.columns)))

    # Ordre inverse : la feuille de donnees en premier doit aussi fonctionner.
    feuilles_inv = {
        "Import": pd.DataFrame({c: [] for c in ["Marche", "Profession", "Age", "MMM", "VRD"]}),
        "Notice": pd.DataFrame({"x": ["texte"]}),
    }
    r.verifier("la feuille de donnees est retenue quel que soit son rang",
               set(COLONNES_OBLIGATOIRES).issubset(set(selectionner_feuille(feuilles_inv).columns)))

    # Repli : un classeur d'une seule feuille conserve le comportement d'origine.
    seule = {"Feuille1": pd.DataFrame({"Marche": [], "Age": [], "MMM": [], "VRD": []})}
    r.verifier("classeur mono-feuille : la feuille est renvoyee telle quelle",
               "Marche" in selectionner_feuille(seule).columns)

    # Aucune feuille conforme : repli sur la premiere (pas d'exception).
    aucune = {"A": pd.DataFrame({"x": [1]}), "B": pd.DataFrame({"y": [2]})}
    r.verifier("aucune feuille conforme -> repli sur la premiere, sans erreur",
               "x" in selectionner_feuille(aucune).columns)

    # ================================================================== #
    # 2. Le VRAI fichier de test livre s'importe et se segmente
    # ================================================================== #
    r.verifier("le fichier de test livre est present dans le depot",
               os.path.exists(FICHIER_TEST))
    if os.path.exists(FICHIER_TEST):
        feuilles_reelles = pd.read_excel(FICHIER_TEST, sheet_name=None)
        r.verifier("  le classeur a bien plusieurs feuilles",
                   len(feuilles_reelles) >= 2)
        df = selectionner_feuille(feuilles_reelles)
        r.verifier("  la feuille retenue contient les colonnes obligatoires",
                   set(COLONNES_OBLIGATOIRES).issubset(set(df.columns)))

        res, inv = segmenter_dataframe(df, MoteurSegmentation())
        # Avant correction : 0 segmentee, 18 invalides.
        r.verifier(f"  des lignes sont SEGMENTEES (obtenu : {len(res)}, avant : 0)",
                   len(res) > 20)
        r.verifier("  la majorite des lignes est valide (avant : 0 sur 18)",
                   len(res) > len(inv))

        # Les seules lignes invalides sont les cas-limites VOULUS du fichier de
        # test (marche non gere, age negatif, montant manquant) : leur presence
        # est correcte, ce sont des cas de controle.
        erreurs = " ".join(str(e) for e in inv.get("Erreurs", []))
        if len(inv):
            r.verifier("  les lignes invalides sont les cas-limites attendus",
                       any(motif in erreurs for motif in ("TPME", "negatif", "manquant")),
                       erreurs[:120])

        # Les segments produits sont ceux du moteur (aucune logique dupliquee).
        segments = set(res["Segment"].dropna())
        r.verifier("  les segments produits sont ceux de la note",
                   segments.issubset({"Haut de Gamme", "Classe Moyenne", "Grand Public",
                                      "Les Jeunes", "Premium", "Potentiel moyen",
                                      "Faible potentiel"}),
                   str(segments))

    return r.bilan()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
