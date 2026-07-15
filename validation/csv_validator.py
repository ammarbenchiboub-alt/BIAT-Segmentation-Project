"""
Validation des donnees d'entree (simulation individuelle et import CSV).

Objectif : garantir que seules des lignes propres sont transmises au moteur.
Les controles portent sur les 7 champs metier utilises par la simulation :
Marche, Profession, Age, MMM, VRD, Nationalite, Residence.
"""
from __future__ import annotations

import math
from typing import Any

COLONNES_ATTENDUES = ["Marche", "Profession", "Age", "MMM", "VRD", "Nationalite", "Residence",
                       "EpargnantDeposantExclusif"]
# 8e champ optionnel : absent ou vide -> False (comportement identique a avant son ajout).
COLONNES_OPTIONNELLES = ["EpargnantDeposantExclusif"]

VALEURS_MARCHE = ["PART", "PRO", "TRE", "ENR"]
VALEURS_RESIDENCE = ["Oui", "Non"]
VALEURS_NATIONALITE = ["Tunisienne", "Autre"]
VALEURS_OUI_NON = ["Oui", "Non"]


def _est_nombre(valeur: Any) -> bool:
    try:
        float(str(valeur).replace(",", "."))
        return True
    except (TypeError, ValueError):
        return False


def _vers_nombre(valeur: Any) -> float:
    return float(str(valeur).replace(",", "."))


def _est_vide(valeur: Any) -> bool:
    """Vrai si la valeur doit etre consideree comme absente : None, chaine
    vide, ou NaN (cellule Excel/CSV laissee vide -> pandas la lit comme un
    float NaN, que float('nan') accepte a tort comme un nombre valide)."""
    if valeur is None:
        return True
    s = str(valeur).strip()
    if s == "":
        return True
    try:
        return math.isnan(float(s.replace(",", ".")))
    except (TypeError, ValueError):
        return False


def valider_ligne(ligne: dict) -> list[str]:
    """Renvoie la liste des erreurs (vide si la ligne est valide)."""
    erreurs: list[str] = []

    # Marche (obligatoire)
    marche = str(ligne.get("Marche", "")).strip().upper()
    if not marche:
        erreurs.append("Marche manquant")
    elif marche not in VALEURS_MARCHE:
        erreurs.append(f"Marche invalide '{marche}' (attendu : {', '.join(VALEURS_MARCHE)})")

    # Age (obligatoire, entier >= 0)
    age = ligne.get("Age")
    if _est_vide(age):
        erreurs.append("Age manquant")
    elif not _est_nombre(age):
        erreurs.append(f"Age non numerique '{age}'")
    elif _vers_nombre(age) < 0:
        erreurs.append("Age negatif")

    # MMM (obligatoire, numerique >= 0)
    mmm = ligne.get("MMM")
    if _est_vide(mmm):
        erreurs.append("MMM manquant")
    elif not _est_nombre(mmm):
        erreurs.append(f"MMM non numerique '{mmm}'")
    elif _vers_nombre(mmm) < 0:
        erreurs.append("MMM negatif")

    # VRD (obligatoire, numerique >= 0)
    vrd = ligne.get("VRD")
    if _est_vide(vrd):
        erreurs.append("VRD manquant")
    elif not _est_nombre(vrd):
        erreurs.append(f"VRD non numerique '{vrd}'")
    elif _vers_nombre(vrd) < 0:
        erreurs.append("VRD negatif")

    # Nationalite (optionnel mais controle si present)
    nat = str(ligne.get("Nationalite", "")).strip()
    if nat and nat.capitalize() not in VALEURS_NATIONALITE:
        erreurs.append(f"Nationalite invalide '{nat}' (attendu : {', '.join(VALEURS_NATIONALITE)})")

    # Residence (optionnel mais controle si present)
    res = str(ligne.get("Residence", "")).strip()
    if res and res.capitalize() not in VALEURS_RESIDENCE:
        erreurs.append(f"Residence invalide '{res}' (attendu : {', '.join(VALEURS_RESIDENCE)})")

    # EpargnantDeposantExclusif (8e champ optionnel, controle si present)
    epargnant = str(ligne.get("EpargnantDeposantExclusif", "")).strip()
    if epargnant and epargnant.capitalize() not in VALEURS_OUI_NON:
        erreurs.append(f"EpargnantDeposantExclusif invalide '{epargnant}' (attendu : {', '.join(VALEURS_OUI_NON)})")

    return erreurs


def normaliser_ligne(ligne: dict) -> dict:
    """Transforme une ligne brute en profil pret pour le moteur."""
    return {
        "Marche": str(ligne.get("Marche", "")).strip().upper(),
        "Profession": str(ligne.get("Profession", "")).strip(),
        "Age": int(_vers_nombre(ligne["Age"])) if _est_nombre(ligne.get("Age")) else None,
        "MMM": _vers_nombre(ligne["MMM"]) if _est_nombre(ligne.get("MMM")) else None,
        "VRD": _vers_nombre(ligne["VRD"]) if _est_nombre(ligne.get("VRD")) else None,
        "Nationalite": str(ligne.get("Nationalite", "")).strip(),
        "Residence": str(ligne.get("Residence", "")).strip(),
        "EpargnantDeposantExclusif": str(ligne.get("EpargnantDeposantExclusif", "")).strip().capitalize() == "Oui",
    }


def valider_dataframe(df) -> tuple:
    """Valide un DataFrame pandas.

    Renvoie (df_valide, df_invalide) ou df_invalide possede une colonne
    'Erreurs' detaillant les problemes de chaque ligne.
    """
    import pandas as pd

    colonnes_presentes = [c for c in COLONNES_ATTENDUES if c in df.columns]
    manquantes = [c for c in COLONNES_ATTENDUES if c not in df.columns]

    lignes_valides, lignes_invalides = [], []
    for idx, row in df.iterrows():
        ligne = {c: row.get(c) for c in colonnes_presentes}
        erreurs = list(valider_ligne(ligne))
        for c in manquantes:
            if c in ("Marche", "Age", "MMM", "VRD"):
                erreurs.append(f"Colonne obligatoire absente : {c}")
        if erreurs:
            r = dict(ligne)
            r["Ligne"] = idx + 2  # +2 : en-tete + index 0
            r["Erreurs"] = " ; ".join(erreurs)
            lignes_invalides.append(r)
        else:
            lignes_valides.append(normaliser_ligne(ligne))

    return pd.DataFrame(lignes_valides), pd.DataFrame(lignes_invalides)
