"""Tests du referentiel BIAT (P3).

Propriete CENTRALE verifiee ici : la page Referentiel est un MIROIR de la
source unique, jamais une copie. Aucune valeur n'y est saisie en dur.

Le test decisif modifie un seuil en memoire et verifie que le referentiel
affiche immediatement la nouvelle valeur : si un seuil avait ete recopie dans
le code de presentation, ce test echouerait.
"""
from __future__ import annotations

import sys

from _outils import Resultats

import referentiel as ref
from core import MoteurSegmentation, charger_regles


def run() -> bool:
    r = Resultats("referentiel BIAT (source unique)")
    moteur = MoteurSegmentation()

    # ================================================================== #
    # 1. Marches et regles : conformes au fichier de regles
    # ================================================================== #
    marches = ref.marches(moteur)
    r.egal("les 4 marches geres sont exposes", len(marches), 4)
    r.egal("  codes attendus", sorted(c for c, _ in marches), ["ENR", "PART", "PRO", "TRE"])
    r.verifier("  chaque marche porte son libelle", all(lib for _, lib in marches))

    total_json = sum(len(c["regles"]) for c in moteur.marches.values())
    r.egal("le compte de regles correspond au JSON", ref.compter_regles(moteur), total_json)

    lignes = ref.table_regles(moteur, "PART")
    r.egal("toutes les regles PART sont restituees",
           len(lignes), len(moteur.marches["PART"]["regles"]))
    r.verifier("  les regles sont triees par priorite",
               [l["Priorite"] for l in lignes] == sorted(l["Priorite"] for l in lignes))
    colonnes = {"Priorite", "Segment", "Sous-segment", "Age", "MMM", "VRD",
                "Condition d'eligibilite", "Identifiant"}
    r.verifier("  chaque ligne expose les colonnes attendues",
               all(colonnes.issubset(set(l)) for l in lignes))

    # Les identifiants restitues sont exactement ceux du JSON.
    ids_json = {x["id"] for x in moteur.marches["PART"]["regles"]}
    r.egal("  identifiants identiques au JSON", {l["Identifiant"] for l in lignes}, ids_json)

    # ================================================================== #
    # 2. TEST DECISIF : le referentiel suit la source unique
    # ================================================================== #
    # Le seuil Fortunes est porte a 600 mD en memoire. S'il etait ecrit en dur
    # dans le module de presentation, l'affichage resterait a 500 mD.
    regles_modifiees = charger_regles()
    for regle in regles_modifiees["marches"]["PART"]["regles"]:
        if regle["id"] == "PART_HDG_FORTUNES":
            regle["conditions"]["vrd"]["min"] = 600_000
    moteur_modifie = MoteurSegmentation(regles=regles_modifiees)

    ligne_fortunes = next(l for l in ref.table_regles(moteur_modifie, "PART")
                          if l["Identifiant"] == "PART_HDG_FORTUNES")
    r.verifier("un seuil modifie apparait immediatement dans le referentiel",
               "600 mD" in ligne_fortunes["VRD"], ligne_fortunes["VRD"])
    r.verifier("  et l'ancienne valeur a disparu", "500 mD" not in ligne_fortunes["VRD"])

    # Valeur d'origine correctement restituee par ailleurs.
    ligne_origine = next(l for l in ref.table_regles(moteur, "PART")
                         if l["Identifiant"] == "PART_HDG_FORTUNES")
    r.verifier("le referentiel non modifie affiche bien 500 mD",
               "500 mD" in ligne_origine["VRD"], ligne_origine["VRD"])

    # ================================================================== #
    # 3. Conversion DT -> mD conforme a la note (1 mD = 1 000 DT)
    # ================================================================== #
    ligne_cm = next(l for l in ref.table_regles(moteur, "PART")
                    if l["Identifiant"] == "PART_CM_SALARIES")
    r.verifier("intervalle formate en mD (1 - 4 mD)",
               "1 mD" in ligne_cm["MMM"] and "4 mD" in ligne_cm["MMM"], ligne_cm["MMM"])

    # Une regle sans contrainte monetaire doit afficher un tiret, pas "0 mD".
    ligne_pl = next((l for l in ref.table_regles(moteur, "PRO")
                     if l["Identifiant"] == "PRO_HDG_PL"), None)
    if ligne_pl:
        r.egal("regle sans seuil MMM -> tiret", ligne_pl["MMM"], "—")
        r.verifier("  et sa condition d'eligibilite est exposee",
                   "profession" in ligne_pl["Condition d'eligibilite"].lower())

    # ================================================================== #
    # 4. Professions, metadonnees, points de vigilance : lus du JSON
    # ================================================================== #
    listes = ref.listes_professions(moteur)
    r.egal("les listes de professions viennent du JSON",
           set(listes), set(moteur.regles["listes_professions"]))
    r.verifier("  chaque liste est non vide", all(v for v in listes.values()))

    meta = dict(ref.metadonnees(moteur))
    r.verifier("la source officielle est citee",
               any("2023-06" in v for v in meta.values()))
    r.verifier("  la combinaison MMM/VRD est documentee comme un OU",
               meta.get("Combinaison MMM / VRD", "").upper() == "OR")
    r.verifier("  l'unite des seuils est precisee", "mD" in meta.get("Unite des seuils", ""))

    points = ref.points_de_vigilance(moteur)
    r.verifier("les points de vigilance du JSON sont exposes (transparence)",
               len(points) > 0)
    r.verifier("  chacun porte un intitule et un texte",
               all(t and x for t, x in points))

    # ================================================================== #
    # 5. Glossaire : couvre les termes indispensables
    # ================================================================== #
    termes = {t for t, _ in ref.GLOSSAIRE}
    for attendu in ("MMM", "VRD", "mD", "PART", "PRO", "TRE", "ENR"):
        r.verifier(f"le glossaire definit '{attendu}'", attendu in termes)
    r.verifier("  chaque terme a une definition non vide",
               all(d.strip() for _, d in ref.GLOSSAIRE))

    # ================================================================== #
    # 6. Lecture seule : le referentiel ne modifie jamais les regles
    # ================================================================== #
    avant = charger_regles()
    ref.table_regles(moteur, "PART")
    ref.listes_professions(moteur)
    ref.metadonnees(moteur)
    ref.points_de_vigilance(moteur)
    r.egal("consulter le referentiel ne modifie pas le fichier de regles",
           charger_regles(), avant)

    return r.bilan()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
