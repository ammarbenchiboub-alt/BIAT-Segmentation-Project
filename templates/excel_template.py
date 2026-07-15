"""
Generation du modele Excel d'import en masse.

Le modele contient des listes deroulantes (data validation) lorsque c'est
possible :
    - Marche      : PART / PRO / TRE / ENR
    - Residence   : Oui / Non
    - Nationalite : Tunisienne / Autre
    - Profession  : liste issue de la note (annexes 4 et 5) + valeurs courantes
    - Age         : entier >= 0
    - MMM, VRD    : saisie libre (numerique, en DT)
"""
from __future__ import annotations

import io
import os

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation

from core import MoteurSegmentation
from validation import (
    COLONNES_ATTENDUES, VALEURS_MARCHE, VALEURS_RESIDENCE, VALEURS_NATIONALITE, VALEURS_OUI_NON,
)

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(_BASE, "templates", "modele_import_biat.xlsx")

_BLEU = "1B3A6B"
_OR = "C9A227"


def _professions_pour_liste() -> list[str]:
    moteur = MoteurSegmentation()
    base = moteur.professions_connues()
    extras = ["Etudiant", "Commercant", "Artisan", "Salarie", "Autre"]
    for e in extras:
        if e not in base:
            base.append(e)
    return base


def generer_template_excel(chemin: str | None = None) -> bytes:
    """Cree le modele et renvoie ses octets. Ecrit aussi sur disque si chemin."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Import"

    # -- En-tetes -----------------------------------------------------------
    entete_fill = PatternFill("solid", fgColor=_BLEU)
    entete_font = Font(color="FFFFFF", bold=True, size=11)
    bord = Border(*[Side(style="thin", color="BBBBBB")] * 4)
    for col, nom in enumerate(COLONNES_ATTENDUES, start=1):
        c = ws.cell(row=1, column=col, value=nom)
        c.fill = entete_fill
        c.font = entete_font
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = bord
        ws.column_dimensions[c.column_letter].width = 18

    # -- Feuille de listes (masquee) ---------------------------------------
    listes = wb.create_sheet("Listes")
    professions = _professions_pour_liste()
    listes["A1"] = "Marche"
    for i, v in enumerate(VALEURS_MARCHE, start=2):
        listes.cell(row=i, column=1, value=v)
    listes["B1"] = "Residence"
    for i, v in enumerate(VALEURS_RESIDENCE, start=2):
        listes.cell(row=i, column=2, value=v)
    listes["C1"] = "Nationalite"
    for i, v in enumerate(VALEURS_NATIONALITE, start=2):
        listes.cell(row=i, column=3, value=v)
    listes["D1"] = "Profession"
    for i, v in enumerate(professions, start=2):
        listes.cell(row=i, column=4, value=v)
    listes.sheet_state = "hidden"

    n = 500  # lignes de saisie couvertes par les validations

    def _ajouter_validation(formule: str, colonne: str, allow_blank=True, custom=None):
        dv = DataValidation(type=custom or "list", formula1=formule, allow_blank=allow_blank, showErrorMessage=True)
        dv.error = "Valeur non autorisee. Choisir dans la liste."
        dv.errorTitle = "Saisie invalide"
        ws.add_data_validation(dv)
        dv.add(f"{colonne}2:{colonne}{n+1}")

    listes["E1"] = "OuiNon"
    for i, v in enumerate(VALEURS_OUI_NON, start=2):
        listes.cell(row=i, column=5, value=v)

    # Marche (col A), Profession (col B), Nationalite (col F), Residence (col G),
    # EpargnantDeposantExclusif (col H, 8e champ optionnel)
    _ajouter_validation(f"=Listes!$A$2:$A${1+len(VALEURS_MARCHE)}", "A", allow_blank=False)
    _ajouter_validation(f"=Listes!$D$2:$D${1+len(professions)}", "B")
    _ajouter_validation(f"=Listes!$C$2:$C${1+len(VALEURS_NATIONALITE)}", "F")
    _ajouter_validation(f"=Listes!$B$2:$B${1+len(VALEURS_RESIDENCE)}", "G")
    _ajouter_validation(f"=Listes!$E$2:$E${1+len(VALEURS_OUI_NON)}", "H")

    # Age (col C) : entier >= 0
    dv_age = DataValidation(type="whole", operator="greaterThanOrEqual", formula1="0", allow_blank=True, showErrorMessage=True)
    dv_age.error = "L'age doit etre un entier >= 0."
    dv_age.errorTitle = "Age invalide"
    ws.add_data_validation(dv_age)
    dv_age.add(f"C2:C{n+1}")

    # MMM (col D), VRD (col E) : decimal >= 0
    for col in ("D", "E"):
        dv = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1="0", allow_blank=True, showErrorMessage=True)
        dv.error = "Montant en DT, valeur >= 0."
        dv.errorTitle = "Montant invalide"
        ws.add_data_validation(dv)
        dv.add(f"{col}2:{col}{n+1}")

    # -- Ligne d'exemple ----------------------------------------------------
    exemple = ["PRO", "Commercant", 40, 90, 3, "Tunisienne", "Oui", "Non"]
    for col, val in enumerate(exemple, start=1):
        cell = ws.cell(row=2, column=col, value=val)
        cell.font = Font(italic=True, color="888888")

    # -- Notice -------------------------------------------------------------
    notice = wb.create_sheet("Notice")
    notice_lignes = [
        "MODELE D'IMPORT - Segmentation BIAT (Note 2023-06)",
        "",
        "Colonnes obligatoires : Marche, Age, MMM, VRD.",
        "Montants MMM et VRD exprimes en DT (dinars). 1 mD = 1000 DT.",
        "Marche : PART, PRO, TRE ou ENR (TPME non gere).",
        "Residence : Oui / Non   |   Nationalite : Tunisienne / Autre.",
        "La ligne 2 est un exemple : la remplacer par vos donnees.",
        "Les colonnes Revenus et Nombre d'operations ne sont pas utilisees.",
        "EpargnantDeposantExclusif (8e champ, optionnel) : Oui / Non. Laisser vide ou 'Non' si non "
        "concerne. Active, pour le marche PART, le sous-segment 'Epargnants et deposants exclusifs'.",
    ]
    for i, txt in enumerate(notice_lignes, start=1):
        c = notice.cell(row=i, column=1, value=txt)
        if i == 1:
            c.font = Font(bold=True, size=13, color=_BLEU)
    notice.column_dimensions["A"].width = 80

    ws.freeze_panes = "A2"

    # -- Sortie -------------------------------------------------------------
    if chemin is None:
        chemin = TEMPLATE_PATH
    wb.save(chemin)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


if __name__ == "__main__":
    data = generer_template_excel()
    print(f"Template genere : {TEMPLATE_PATH} ({len(data)} octets)")
