"""
REFERENTIEL BIAT — restitution lisible des regles de segmentation.

Ce module met en forme, pour consultation, le contenu de
config/regles_segmentation.json : seuils par marche, listes de professions,
metadonnees et points d'ambiguite de la note.

SOURCE UNIQUE : rien n'est saisi en dur ici. Chaque valeur affichee est LUE
dans le fichier de regles via le moteur. Une modification validee en page
Parametrage (double validation) se repercute donc immediatement dans le
referentiel — c'est precisement ce que cette page donne a voir.

Ce module ne contient aucune logique de segmentation : il ne fait que
presenter. Il n'importe pas Streamlit, ce qui le rend testable sans interface.
"""
from __future__ import annotations

from typing import Any

from commun import en_mD

# Termes du domaine. Les DEFINITIONS reprennent les libelles deja utilises
# dans l'application (formulaire de simulation) et les metadonnees du fichier
# de regles ; aucune notion nouvelle n'est introduite ici.
GLOSSAIRE = [
    ("MMM", "Mouvements mensuels moyens (en dinars) : flux crediteurs moyens "
            "constates sur le compte du client."),
    ("VRD", "Total des avoirs stables (en dinars) : encours d'epargne et de "
            "depots detenus par le client."),
    ("mD", "Millier de dinars. 1 mD = 1 000 DT. Unite de lecture des seuils "
           "dans la note ; le fichier de regles, lui, stocke des dinars."),
    ("PBD", "Perimetre de la clientele concernee par la note de segmentation."),
    ("PART", "Marche des Particuliers."),
    ("PRO", "Marche des Professionnels."),
    ("TRE", "Tunisiens Residents a l'Etranger."),
    ("ENR", "Etrangers Non Residents."),
    ("Sous-segment", "Subdivision d'un segment ; c'est le niveau le plus fin "
                     "attribue par le moteur."),
    ("Priorite", "Ordre d'evaluation des regles. Le moteur retient la PREMIERE "
                 "regle satisfaite ; une priorite plus faible est donc "
                 "evaluee plus tot."),
]


def _borne_texte(bornes: dict | None, unite_mD: bool = True) -> str:
    """Ecriture lisible d'un intervalle : '>= 100 mD', '< 5 mD', '100 - 300 mD'.
    Renvoie un tiret si la variable n'est pas contrainte."""
    bornes = bornes or {}
    mini, maxi = bornes.get("min"), bornes.get("max")
    fmt = en_mD if unite_mD else (lambda v: str(v))
    if mini is None and maxi is None:
        return "—"
    if mini is not None and maxi is not None:
        return f"{fmt(mini)} – {fmt(maxi)}" if unite_mD else f"{mini} – {maxi}"
    if mini is not None:
        return f"≥ {fmt(mini)}"
    return f"< {fmt(maxi)}"


def _age_texte(bornes: dict | None) -> str:
    bornes = bornes or {}
    mini, maxi = bornes.get("min"), bornes.get("max")
    if mini is None and maxi is None:
        return "—"
    if mini is not None and maxi is not None:
        return f"{mini} – {maxi} ans"
    if mini is not None:
        return f"{mini} ans et +"
    return f"≤ {maxi} ans"


def table_regles(moteur: Any, marche: str) -> list[dict]:
    """Regles d'un marche, triees par priorite, pretes a l'affichage."""
    contenu = moteur.marches.get(marche)
    if not contenu:
        return []
    lignes = []
    for regle in sorted(contenu["regles"], key=lambda r: r.get("priorite", 999)):
        conditions = regle.get("conditions", {})
        exigences = []
        if conditions.get("profession_in"):
            exigences.append(f"Profession dans « {conditions['profession_in']} »")
        if conditions.get("epargnant_deposant_exclusif"):
            exigences.append("Epargnant / deposant exclusif")
        lignes.append({
            "Priorite": regle.get("priorite"),
            "Segment": regle.get("segment", ""),
            "Sous-segment": regle.get("sous_segment", ""),
            "Age": _age_texte(conditions.get("age")),
            "MMM": _borne_texte(conditions.get("mmm")),
            "VRD": _borne_texte(conditions.get("vrd")),
            "Condition d'eligibilite": " ; ".join(exigences) if exigences else "—",
            "Identifiant": regle.get("id", ""),
        })
    return lignes


def marches(moteur: Any) -> list[tuple[str, str]]:
    """Marches geres : (code, libelle), dans l'ordre du fichier de regles."""
    return [(code, contenu.get("libelle", code))
            for code, contenu in moteur.marches.items()]


def listes_professions(moteur: Any) -> dict[str, list[str]]:
    """Listes de professions (annexes 4 et 5) telles que definies dans le JSON."""
    return dict(moteur.regles.get("listes_professions", {}))


def metadonnees(moteur: Any) -> list[tuple[str, str]]:
    """Metadonnees de la note : source, version, unite, perimetre, champs.
    Lues dans `meta`, jamais reecrites."""
    meta = moteur.regles.get("meta", {})
    infos: list[tuple[str, str]] = []

    def ajouter(libelle: str, cle: str) -> None:
        valeur = meta.get(cle)
        if valeur in (None, "", [], {}):
            return
        infos.append((libelle, ", ".join(valeur) if isinstance(valeur, list) else str(valeur)))

    ajouter("Source", "source")
    ajouter("Reference anterieure", "reference_anterieure")
    ajouter("Version du referentiel", "version")
    ajouter("Unite des seuils", "unite_seuils")
    ajouter("Combinaison MMM / VRD", "logique_mmm_vrd")
    ajouter("Marches geres", "marches_geres")
    ajouter("Marches exclus", "marches_exclus")
    ajouter("Champs de simulation", "champs_simulation_individuelle")
    ajouter("Champs non utilises", "champs_non_utilises")
    return infos


def points_de_vigilance(moteur: Any) -> list[tuple[str, str]]:
    """Points d'ambiguite ou de verification consignes dans le fichier de
    regles (`_notes_conflits`). Les exposer relève de la transparence
    methodologique : ils documentent les choix d'interpretation de la note."""
    notes = moteur.regles.get("_notes_conflits", {})
    return [(cle.replace("_", " "), str(valeur)) for cle, valeur in notes.items()]


def compter_regles(moteur: Any) -> int:
    """Nombre total de regles du referentiel, tous marches confondus."""
    return sum(len(contenu.get("regles", [])) for contenu in moteur.marches.values())
