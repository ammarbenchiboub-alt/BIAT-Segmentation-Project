"""
SMART RESPONSE RENDERER — Planificateur (couche de presentation pure).

Role
----
Transformer une reponse DEJA CALCULEE par le chatbot
(`chatbot.expert.ChatbotExpert.repondre`) en une liste de BLOCS d'affichage
abstraits, sans produire aucun rendu concret. Le rendu Streamlit est realise
separement par `presentation.rendu` a partir de ces blocs.

Principe d'architecture
-----------------------
Ce module ne contient AUCUNE logique metier et n'importe NI streamlit NI le
moteur de segmentation. Il ne DECIDE jamais d'un segment : il se contente de
choisir la meilleure MISE EN FORME d'une reponse existante. Cette separation a
deux benefices :

  1. La "decision de mise en forme" (quel composant pour quelle reponse) est
     une fonction pure, donc entierement testable sans interface graphique —
     c'est la que reside l'intelligence du moteur de rendu.
  2. Ajouter un nouveau composant visuel ne demande de toucher ni au chatbot,
     ni a la logique metier : il suffit d'ajouter un type de bloc ici et son
     rendu dans presentation.rendu.

Garantie de non-modification fonctionnelle : le contenu textuel des reponses
n'est jamais reecrit ni recalcule. Le planificateur ne fait que STRUCTURER ce
que le chatbot a deja produit (le decouper, l'etiqueter, en extraire des
valeurs pour l'affichage). En cas de doute, il retombe toujours sur un affichage
texte simple : il ne peut donc jamais degrader la lisibilite en dessous de
l'existant.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# --------------------------------------------------------------------------- #
# Modele de blocs d'affichage
# --------------------------------------------------------------------------- #
@dataclass
class Bloc:
    """Bloc d'affichage abstrait. Sous-classe par type de composant."""


@dataclass
class Titre(Bloc):
    texte: str


@dataclass
class Texte(Bloc):
    texte: str


@dataclass
class Callout(Bloc):
    """Encadre d'information. `ton` pilote la couleur (info/succes/attention/
    danger/neutre)."""
    texte: str
    ton: str = "info"
    icone: str = ""


@dataclass
class CarteDecision(Bloc):
    """Carte de synthese d'une decision de segmentation."""
    segment: str | None
    sous_segment: str | None
    regle_id: str | None


@dataclass
class ItemKPI:
    label: str
    valeur: str
    hint: str = ""
    icone: str = ""


@dataclass
class GroupeKPI(Bloc):
    items: list[ItemKPI]


@dataclass
class ItemCheck:
    texte: str
    ok: bool = True


@dataclass
class Checklist(Bloc):
    items: list[ItemCheck]
    titre: str = "Conditions verifiees"


@dataclass
class ItemListe:
    titre: str
    detail: str = ""


@dataclass
class ListeStructuree(Bloc):
    items: list[ItemListe]
    titre: str | None = None


@dataclass
class Badges(Bloc):
    """Suite de pastilles (chips). Utilise pour un contexte compact ou une
    enumeration courte (professions, criteres)."""
    items: list[str]
    ton: str = "neutre"


@dataclass
class Reference(Bloc):
    source: str


@dataclass
class Accordeon(Bloc):
    titre: str
    blocs: list = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Utilitaires (presentation uniquement)
# --------------------------------------------------------------------------- #
def _val(res: Any, cle: str, defaut: Any = None) -> Any:
    """Accede a un champ que `res` soit un dataclass (ResultatSegmentation) ou
    un dict. Evite d'importer core dans la couche de presentation."""
    if isinstance(res, dict):
        return res.get(cle, defaut)
    return getattr(res, cle, defaut)


def _fmt_montant(valeur: Any) -> str:
    """Formate un montant avec separateur de milliers a la francaise
    (550000 -> '550 000'). Purement presentationnel."""
    try:
        n = float(valeur)
    except (TypeError, ValueError):
        return str(valeur)
    if n == int(n):
        n = int(n)
    # Espace INSECABLE (U+00A0) comme separateur de milliers : typographie
    # francaise correcte, et un montant ne se coupe pas en fin de ligne.
    return f"{n:,}".replace(",", " ")


def _kpis_profil(profil: dict) -> list[ItemKPI]:
    """Cartes KPI pour les valeurs NUMERIQUES du profil (Age, MMM, VRD).

    Les valeurs monetaires MMM/VRD, qui commandent la segmentation, meritent un
    affichage chiffre lisible plutot que noyees dans une phrase."""
    items: list[ItemKPI] = []
    age = profil.get("Age")
    if age not in (None, ""):
        items.append(ItemKPI("Age", str(age), "ans", "🎂"))
    if profil.get("MMM") not in (None, ""):
        items.append(ItemKPI("MMM", _fmt_montant(profil["MMM"]), "DT", "💳"))
    if profil.get("VRD") not in (None, ""):
        items.append(ItemKPI("VRD (avoirs)", _fmt_montant(profil["VRD"]), "DT", "🏦"))
    return items


def _badges_contexte(profil: dict) -> list[str]:
    """Pastilles de contexte (categoriel) : marche, profession, nationalite,
    residence. Compact, sans occuper une carte KPI chacun."""
    badges: list[str] = []
    if profil.get("Marche"):
        badges.append(f"Marche {profil['Marche']}")
    prof = profil.get("Profession")
    if prof and str(prof).strip() and str(prof).strip().lower() != "autre":
        badges.append(str(prof).strip())
    nat = profil.get("Nationalite")
    if nat and str(nat).strip():
        badges.append(str(nat).strip())
    res = profil.get("Residence")
    if res and str(res).strip():
        badges.append("Resident" if str(res).strip().lower().startswith("oui") else "Non resident")
    return badges


def _conditions(explications: list[str], regle_id: str | None) -> list[ItemCheck]:
    """Transforme la trace du moteur en checklist des conditions de la REGLE
    RETENUE uniquement.

    Le moteur trace l'evaluation de toutes les regles essayees ; on ne conserve
    que les lignes prefixees par l'identifiant de la regle finalement retenue
    (`[REGLE_ID] ...`), ce qui donne exactement "les conditions verifiees" pour
    la decision affichee. Aucun recalcul : on lit la trace deja produite."""
    if not regle_id:
        return []
    prefixe = f"[{regle_id}]"
    items: list[ItemCheck] = []
    for ligne in explications or []:
        l = ligne.strip()
        if not l.startswith(prefixe):
            continue
        contenu = l.split("]", 1)[1].strip() if "]" in l else l
        ok = any(marqueur in l for marqueur in ("OK", "MATCH", "validee"))
        items.append(ItemCheck(contenu, ok))
    return items


def _detecter_liste(texte: str) -> tuple[str | None, list[ItemListe]] | None:
    """Detecte une reponse structuree en plusieurs elements separes par ' ; '.

    Reconnait par exemple 'TRE : Premium (...) ; Potentiel moyen (...) ; ...' et
    en fait une liste titree. Retourne None si aucune structure de ce type
    n'est presente (la reponse reste alors un simple encadre). Detection
    conservatrice : au moindre doute, on n'impose pas de structure.
    """
    corps = texte.strip().rstrip(".")
    if " ; " not in corps:
        return None

    titre: str | None = None
    # Un prefixe 'X : ...' precedant le premier separateur devient le titre.
    avant_premier = corps.split(" ; ", 1)[0]
    if " : " in avant_premier:
        titre, corps = corps.split(" : ", 1)

    parts = [p.strip() for p in corps.split(" ; ") if p.strip()]
    if len(parts) < 2:
        return None

    items: list[ItemListe] = []
    for p in parts:
        p = p.strip().rstrip(".")
        if "(" in p:
            t, d = p.split("(", 1)
            items.append(ItemListe(t.strip(), "(" + d.strip()))
        elif " : " in p:
            t, d = p.split(" : ", 1)
            items.append(ItemListe(t.strip(), d.strip()))
        else:
            items.append(ItemListe(p.strip()))
    return (titre.strip() if titre else None), items


def _detecter_enumeration(texte: str) -> tuple[str, list[str]] | None:
    """Detecte une enumeration finale 'intro : a, b, c, d, ...' (>= 4 elements
    courts), typiquement une liste de professions. La rend sous forme de
    pastilles plutot qu'en pave de texte. None si non applicable."""
    if " : " not in texte:
        return None
    intro, tail = texte.rsplit(" : ", 1)
    items = [x.strip().rstrip(".") for x in tail.split(",")]
    items = [x for x in items if x]
    if len(items) >= 4 and all(len(x) <= 60 for x in items):
        return intro.strip(), items
    return None


# --------------------------------------------------------------------------- #
# Planificateurs par type de reponse
# --------------------------------------------------------------------------- #
def _planifier_decision(rep: dict) -> list[Bloc]:
    """Aide a la decision : la reponse porte un ResultatSegmentation structure.
    On produit une carte de decision, le contexte, les valeurs cles (KPI), les
    conditions verifiees et la reference — le schema demande explicitement :
    Decision / Justification / Conditions verifiees / Reference."""
    res = rep.get("resultat")
    blocs: list[Bloc] = [Titre("Resultat de la segmentation")]

    if _val(res, "succes"):
        blocs.append(CarteDecision(
            _val(res, "segment"), _val(res, "sous_segment"), _val(res, "regle_id")
        ))
    else:
        blocs.append(Callout(
            _val(res, "message") or "Aucune regle de la note ne correspond a ce profil.",
            ton="attention", icone="⚠️",
        ))

    profil = _val(res, "profil") or {}
    contexte = _badges_contexte(profil)
    if contexte:
        blocs.append(Badges(contexte))

    kpis = _kpis_profil(profil)
    if kpis:
        blocs.append(GroupeKPI(kpis))

    conditions = _conditions(_val(res, "explications") or [], _val(res, "regle_id"))
    if conditions:
        blocs.append(Checklist(conditions))

    source = rep.get("source")
    if source:
        blocs.append(Reference(source))
    return blocs


def _planifier_paragraphe(paragraphe: str, enumerations_vues: set) -> list[Bloc]:
    """Choisit le composant d'UN paragraphe de reponse :
      - liste structuree s'il enumere plusieurs elements (' ; ') ;
      - pastilles s'il se termine par une enumeration (professions...) ;
      - sinon un encadre de reference simple.

    `enumerations_vues` permet d'eviter d'afficher deux fois la meme
    enumeration : le chatbot peut renvoyer deux entrees de connaissance qui
    citent la meme liste (ex. deux definitions des professions liberales). On
    saute alors le paragraphe redondant plutot que de repeter les pastilles.
    """
    liste = _detecter_liste(paragraphe)
    if liste is not None:
        titre, items = liste
        return [ListeStructuree(items, titre)]

    enumeration = _detecter_enumeration(paragraphe)
    if enumeration is not None:
        intro, items = enumeration
        cle = tuple(items)
        if cle in enumerations_vues:
            return []  # enumeration deja affichee -> on ne la repete pas
        enumerations_vues.add(cle)
        return [Callout(intro + " :", ton="info", icone="📘"), Badges(items, ton="bleu")]

    return [Callout(paragraphe, ton="info", icone="📘")]


def _planifier_connaissance(rep: dict) -> list[Bloc]:
    """Reponse issue de la base de connaissances (texte). Chaque paragraphe
    (separe par une ligne vide) est mis en forme independamment, ce qui evite
    qu'une reponse composee de plusieurs entrees soit traitee en bloc et
    produise un encadre demesure."""
    texte = rep.get("reponse", "")
    source = rep.get("source")

    paragraphes = [p.strip() for p in texte.split("\n\n") if p.strip()]
    if not paragraphes:
        paragraphes = [texte]

    blocs: list[Bloc] = []
    enumerations_vues: set = set()
    for paragraphe in paragraphes:
        blocs.extend(_planifier_paragraphe(paragraphe, enumerations_vues))

    if not blocs:  # securite : jamais de reponse vide
        blocs = [Callout(texte, ton="info", icone="📘")]
    if source:
        blocs.append(Reference(source))
    return blocs


def planifier_reponse(rep: dict) -> list[Bloc]:
    """Point d'entree du moteur de rendu : reponse du chatbot -> liste de blocs.

    Fonction TOTALE : elle renvoie toujours au moins un bloc et ne leve jamais
    d'exception, quel que soit le contenu de `rep`. C'est la garantie qui permet
    de la brancher sans risque dans l'interface.
    """
    if not isinstance(rep, dict):
        return [Texte(str(rep))]

    type_reponse = rep.get("type")
    try:
        if type_reponse == "aide_decision":
            return _planifier_decision(rep)
        if type_reponse == "connaissance":
            return _planifier_connaissance(rep)
        if type_reponse == "absent":
            return [Callout(rep.get("reponse", ""), ton="attention", icone="ℹ️")]
        if type_reponse == "vide":
            return [Callout(rep.get("reponse", ""), ton="neutre", icone="💬")]
    except Exception:  # noqa: BLE001 - la presentation ne doit jamais casser l'app
        pass

    # Repli universel : texte brut + source eventuelle. Jamais pire que l'existant.
    blocs: list[Bloc] = [Texte(rep.get("reponse", ""))]
    if rep.get("source"):
        blocs.append(Reference(rep["source"]))
    return blocs
