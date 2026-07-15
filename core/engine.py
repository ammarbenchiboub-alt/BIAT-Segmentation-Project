"""
====================================================================
 MOTEUR UNIQUE DE SEGMENTATION - BIAT (Note 2023-06)
====================================================================
Il n'existe qu'UN SEUL moteur de segmentation dans toute l'application.
Le simulateur individuel, l'import CSV en masse, le chatbot expert et
l'assistant IA appellent TOUS ce meme moteur. Il est interdit de creer
une seconde logique de segmentation ailleurs.

Regle fondamentale : la combinaison MMM / VRD utilise un OU logique (OR),
jamais un ET (AND). Voir la note : marche ENR -> "MMM ou Total des avoirs".

Champs utilises (simulation individuelle) :
    Marche, Profession, Age, MMM, VRD, Nationalite, Residence.
Champ optionnel (8e champ, desactive par defaut) :
    EpargnantDeposantExclusif (bool) - active les sous-segments PART
    "Epargnants et deposants exclusifs" (Affluent / Classe Moyenne / Grand
    Public) prevus par la note pour les clients ne detenant que des comptes
    Epargne / Depots a terme. Valeur par defaut : False (comportement
    identique a avant si le champ n'est pas fourni).
Champs volontairement non utilises : Revenus, Nombre d'operations.

Unite des seuils : DT (dinars). 1 mD = 1000 DT.
====================================================================
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field, asdict
from typing import Any

from .rules_loader import charger_regles


# ---------------------------------------------------------------------------
# Utilitaires
# ---------------------------------------------------------------------------
def _normaliser(texte: Any) -> str:
    """Minuscule + suppression des accents + espaces reduits.

    Permet de comparer 'Medecins generalistes' et 'Médecins  Généralistes'.
    """
    if texte is None:
        return ""
    texte = str(texte).strip().lower()
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return " ".join(texte.split())


MARCHES_VALIDES = ("PART", "PRO", "TRE", "ENR")


# ---------------------------------------------------------------------------
# Structures de resultat
# ---------------------------------------------------------------------------
@dataclass
class ResultatSegmentation:
    """Resultat renvoye par le moteur unique."""

    marche: str
    segment: str | None
    sous_segment: str | None
    regle_id: str | None
    succes: bool
    explications: list[str] = field(default_factory=list)
    profil: dict = field(default_factory=dict)
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Le moteur
# ---------------------------------------------------------------------------
class MoteurSegmentation:
    """Moteur unique. Instancier une fois, reutiliser partout."""

    def __init__(self, regles: dict | None = None):
        self.regles = regles or charger_regles()
        self._listes = self.regles.get("listes_professions", {})

    # -- acces pratiques -----------------------------------------------------
    @property
    def marches(self) -> dict:
        return self.regles["marches"]

    def liste_professions(self, nom_liste: str) -> list[str]:
        return self._listes.get(nom_liste, [])

    def professions_connues(self) -> list[str]:
        """Union dedupliquee de toutes les professions citees par la note."""
        vues, resultat = set(), []
        for valeurs in self._listes.values():
            for prof in valeurs:
                cle = _normaliser(prof)
                if cle not in vues:
                    vues.add(cle)
                    resultat.append(prof)
        return sorted(resultat)

    # -- tests unitaires de conditions --------------------------------------
    @staticmethod
    def _test_intervalle(valeur: float | None, borne: dict) -> tuple[bool, bool]:
        """Renvoie (est_contraint, satisfait) pour une variable monetaire.

        Convention de la note : min inclusif (>=), max exclusif (<).
        """
        mini, maxi = borne.get("min"), borne.get("max")
        contraint = mini is not None or maxi is not None
        if not contraint:
            return False, False
        if valeur is None:
            return True, False
        ok = True
        if mini is not None:
            ok = ok and valeur >= mini
        if maxi is not None:
            ok = ok and valeur < maxi
        return True, ok

    def _profession_dans(self, profession: Any, nom_liste: str) -> bool:
        cible = _normaliser(profession)
        if not cible:
            return False
        return cible in {_normaliser(p) for p in self.liste_professions(nom_liste)}

    # -- evaluation d'une regle ---------------------------------------------
    def _evaluer_regle(self, regle: dict, profil: dict, trace: list[str]) -> bool:
        cond = regle["conditions"]
        rid = regle["id"]

        # 1) Gate profession (AND)
        nom_liste = cond.get("profession_in")
        if nom_liste:
            if not self._profession_dans(profil.get("Profession"), nom_liste):
                return False
            trace.append(f"[{rid}] profession appartient a '{nom_liste}' : OK")

        # 1bis) Gate epargnant/deposant exclusif (AND) - champ optionnel (8e champ)
        exige_epargnant = cond.get("epargnant_deposant_exclusif")
        if exige_epargnant:
            valeur = bool(profil.get("EpargnantDeposantExclusif", False))
            if not valeur:
                return False
            trace.append(f"[{rid}] client epargnant/deposant exclusif : OK")

        # 2) Gate age (AND)
        age = profil.get("Age")
        borne_age = cond.get("age", {})
        amin, amax = borne_age.get("min"), borne_age.get("max")
        if amin is not None or amax is not None:
            if age is None:
                return False
            if amin is not None and age < amin:
                return False
            if amax is not None and age > amax:
                return False
            trace.append(f"[{rid}] age {age} dans bornes [{amin}, {amax}] : OK")

        # 3) Condition monetaire MMM OU VRD (OR)
        mmm = profil.get("MMM")
        vrd = profil.get("VRD")
        c_mmm, ok_mmm = self._test_intervalle(mmm, cond.get("mmm", {}))
        c_vrd, ok_vrd = self._test_intervalle(vrd, cond.get("vrd", {}))

        if not (c_mmm or c_vrd):
            # Aucune contrainte monetaire : la regle repose sur profession/age.
            trace.append(f"[{rid}] pas de contrainte MMM/VRD -> validee par profession/age")
            return True

        satisfait = (c_mmm and ok_mmm) or (c_vrd and ok_vrd)
        details = []
        if c_mmm:
            details.append(f"MMM={mmm} {'OK' if ok_mmm else 'NON'}")
        if c_vrd:
            details.append(f"VRD={vrd} {'OK' if ok_vrd else 'NON'}")
        trace.append(f"[{rid}] {' OU '.join(details)} => {'MATCH' if satisfait else 'rejet'}")
        return satisfait

    # -- API publique --------------------------------------------------------
    def segmenter(self, profil: dict) -> ResultatSegmentation:
        """Segmente UN profil client et renvoie un ResultatSegmentation."""
        trace: list[str] = []
        marche = (profil.get("Marche") or "").upper().strip()

        if marche not in MARCHES_VALIDES:
            return ResultatSegmentation(
                marche=marche, segment=None, sous_segment=None, regle_id=None,
                succes=False, explications=trace, profil=dict(profil),
                message=f"Marche '{marche}' non gere. Marches valides : {', '.join(MARCHES_VALIDES)}.",
            )

        regles = sorted(self.marches[marche]["regles"], key=lambda r: r.get("priorite", 999))
        trace.append(f"Marche {marche} ({self.marches[marche]['libelle']}) - {len(regles)} regles evaluees par priorite.")

        for regle in regles:
            if self._evaluer_regle(regle, profil, trace):
                trace.append(f"=> Regle retenue : {regle['id']} -> {regle['segment']} / {regle['sous_segment']}")
                return ResultatSegmentation(
                    marche=marche, segment=regle["segment"], sous_segment=regle["sous_segment"],
                    regle_id=regle["id"], succes=True, explications=trace, profil=dict(profil),
                    message="Segmentation effectuee.",
                )

        return ResultatSegmentation(
            marche=marche, segment=None, sous_segment=None, regle_id=None,
            succes=False, explications=trace, profil=dict(profil),
            message="Aucune regle de la note ne correspond a ce profil. Clarification requise.",
        )


# ---------------------------------------------------------------------------
# Instance partagee + fonction de commodite
# ---------------------------------------------------------------------------
_MOTEUR_PARTAGE: MoteurSegmentation | None = None


def _moteur() -> MoteurSegmentation:
    global _MOTEUR_PARTAGE
    if _MOTEUR_PARTAGE is None:
        _MOTEUR_PARTAGE = MoteurSegmentation()
    return _MOTEUR_PARTAGE


def segmenter(profil: dict) -> ResultatSegmentation:
    """Raccourci : segmente un profil avec l'instance moteur partagee."""
    return _moteur().segmenter(profil)
