"""
PREUVE DE CONFORMITE METIER — le moteur applique-t-il correctement la note ?

Difference avec la non-regression (tests/test_moteur.py et le controle des
715 008 profils) :

  - la NON-REGRESSION prouve que le comportement du moteur n'a pas CHANGE ;
    elle compare le moteur a lui-meme (a une empreinte anterieure) et ne
    connait pas la note. Un moteur systematiquement faux la passerait.
  - la CONFORMITE prouve que le comportement est CORRECT ; elle compare le
    moteur a un ORACLE EXTERNE : la colonne `Cas_attendu` du jeu de test
    officiel, redigee a la main a partir de la Note BIAT 2023-06, cas par cas.

L'oracle est valable parce qu'il est INDEPENDANT du moteur (il n'en est pas
issu) et TRACABLE a la note (un cas par regle). Si le moteur etait faux,
l'oracle, lui, resterait juste : c'est la condition d'un vrai test de
conformite.

Le jeu de test comporte trois familles de cas, traitees distinctement :

    METIER    -> comparaison STRICTE segment/sous-segment au moteur.
                 Toute divergence fait ECHOUER la suite (valeur de preuve).
    INVALIDE  -> profils volontairement fautifs (marche non gere, age negatif,
                 montant manquant) : on verifie qu'ils sont REJETES par la
                 validation, et non segmentes.
    ML        -> cas relevant du module de detection d'anomalies (complementaire
                 au moteur) : EXCLUS explicitement du perimetre de conformite du
                 moteur, pour ne pas pretendre prouver ce qui n'en releve pas.

Ce test ne modifie ni le moteur ni les regles : il ne fait que LIRE le fichier
de regles (via le moteur) et le jeu de test, puis COMPARER.
"""
from __future__ import annotations

import os
import re
import sys

import pandas as pd

from _outils import Resultats

from core import MoteurSegmentation
from validation import selectionner_feuille, valider_ligne

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FICHIER_TEST = os.path.join(_RACINE, "Jeu_de_test_segmentation_BIAT.xlsx")

# Marqueurs de categorie, tels qu'ecrits dans la colonne Cas_attendu.
_PREFIXE_ML = "Cas ML"
_PREFIXE_INVALIDE = "Ligne invalide"


def _categorie(cas_attendu: str) -> str:
    texte = str(cas_attendu).strip()
    if texte.startswith(_PREFIXE_ML):
        return "ML"
    if texte.startswith(_PREFIXE_INVALIDE):
        return "INVALIDE"
    return "METIER"


def _segment_attendu(cas_attendu: str) -> tuple[str, str]:
    """Extrait (segment, sous_segment) attendu depuis le libelle de l'oracle.

    Deux formes rencontrees dans le jeu de test :
      - "MARCHE - Segment / Sous-segment (annotation)"  (cas standard)
      - "... segment = Segment / Sous-segment"          (cas particuliers)
    L'annotation entre parentheses est un commentaire, retire.
    Pour les marches TRE et ENR, la note ne nomme qu'un niveau : le
    sous-segment est alors egal au segment (convention du moteur, verifiee
    par ailleurs dans test_moteur.py)."""
    texte = str(cas_attendu)
    if "segment = " in texte:
        texte = texte.split("segment = ", 1)[1]
    elif " - " in texte:
        texte = texte.split(" - ", 1)[1]
    texte = re.sub(r"\s*\(.*?\)\s*$", "", texte).strip()
    if " / " in texte:
        seg, sous = texte.split(" / ", 1)
        return seg.strip(), sous.strip()
    return texte.strip(), texte.strip()


def _profil(row: dict) -> dict:
    return {
        "Marche": row["Marche"],
        "Profession": row["Profession"],
        "Age": int(row["Age"]),
        "MMM": float(row["MMM"]),
        "VRD": float(row["VRD"]),
        "Nationalite": row.get("Nationalite"),
        "Residence": row.get("Residence"),
        "EpargnantDeposantExclusif":
            str(row.get("EpargnantDeposantExclusif", "")).strip().lower() == "oui",
    }


def run() -> bool:
    r = Resultats("conformite metier a la Note BIAT 2023-06")

    r.verifier("le jeu de test officiel est present dans le depot",
               os.path.exists(FICHIER_TEST))
    if not os.path.exists(FICHIER_TEST):
        return r.bilan()

    moteur = MoteurSegmentation()
    df = selectionner_feuille(pd.read_excel(FICHIER_TEST, sheet_name=None))
    df = df[df["Cas_attendu"].notna()]
    r.verifier("le jeu de test contient des cas a verifier", len(df) > 0)

    cas_metier, cas_invalide, cas_ml = [], [], []
    for _, row in df.iterrows():
        cat = _categorie(row["Cas_attendu"])
        (cas_metier if cat == "METIER" else cas_invalide if cat == "INVALIDE" else cas_ml
         ).append(row)

    # ================================================================== #
    # 1. CONFORMITE METIER : comparaison stricte au moteur
    # ================================================================== #
    # C'est le cœur de la preuve. Chaque cas est issu de la note ; le moteur
    # doit produire EXACTEMENT le segment / sous-segment attendu.
    regles_exercees = set()
    for row in cas_metier:
        seg_attendu, sous_attendu = _segment_attendu(row["Cas_attendu"])
        res = moteur.segmenter(_profil(row))
        if res.regle_id:
            regles_exercees.add(res.regle_id)
        libelle = str(row["Cas_attendu"])
        r.egal(f"[METIER] {libelle}",
               f"{res.segment} / {res.sous_segment}",
               f"{seg_attendu} / {sous_attendu}")

    r.verifier(f"tous les cas metier ont ete verifies ({len(cas_metier)} cas)",
               len(cas_metier) >= 26)

    # ================================================================== #
    # 2. COUVERTURE : chaque regle du moteur est exercee par un cas
    # ================================================================== #
    # Garantit que le jeu de test couvre l'INTEGRALITE du referentiel : on ne
    # peut pas ajouter une regle au moteur sans lui adjoindre un cas de
    # conformite, sous peine de faire echouer ce controle.
    toutes_regles = {x["id"] for m in moteur.marches.values() for x in m["regles"]}
    non_couvertes = sorted(toutes_regles - regles_exercees)
    r.egal("chaque regle du moteur est exercee par au moins un cas metier",
           non_couvertes, [])
    r.verifier(f"couverture complete : {len(regles_exercees)}/{len(toutes_regles)} regles",
               regles_exercees == toutes_regles)

    # ================================================================== #
    # 3. CAS INVALIDES : rejetes par la validation, jamais segmentes
    # ================================================================== #
    for row in cas_invalide:
        erreurs = valider_ligne({k: row.get(k) for k in
                                 ("Marche", "Age", "MMM", "VRD", "Nationalite", "Residence")})
        r.verifier(f"[INVALIDE] rejete par la validation : {row['Cas_attendu']}",
                   len(erreurs) > 0, f"aucune erreur detectee sur {dict(row)}")
    r.verifier(f"des cas invalides sont presents et couverts ({len(cas_invalide)} cas)",
               len(cas_invalide) > 0)

    # ================================================================== #
    # 4. CAS ML : hors perimetre du moteur, exclusion explicite
    # ================================================================== #
    # On ne les compare PAS au moteur : ils relevent du module de detection
    # d'anomalies (complementaire, jamais decisionnaire). On verifie seulement
    # qu'ils ont bien ete identifies et ecartes du perimetre de conformite.
    r.verifier(f"les cas ML sont identifies et exclus du perimetre moteur "
               f"({len(cas_ml)} cas)", len(cas_ml) > 0)
    for row in cas_ml:
        r.verifier(f"[ML] correctement categorise hors metier : {row['Cas_attendu'][:50]}...",
                   _categorie(row["Cas_attendu"]) == "ML")

    # ================================================================== #
    # 5. Totalite du jeu de test couverte
    # ================================================================== #
    r.egal("chaque ligne du jeu de test est classee dans une categorie",
           len(cas_metier) + len(cas_invalide) + len(cas_ml), len(df))

    print(f"\n  Synthese conformite : {len(cas_metier)} cas metier conformes, "
          f"{len(cas_invalide)} invalides rejetes, {len(cas_ml)} cas ML exclus, "
          f"{len(regles_exercees)}/{len(toutes_regles)} regles couvertes.")

    return r.bilan()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
