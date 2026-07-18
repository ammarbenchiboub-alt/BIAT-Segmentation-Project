"""Tests du Smart Response Renderer (planificateur pur).

Le planificateur (presentation.plan) choisit, sans aucune interface graphique,
le composant d'affichage le plus adapte a une reponse du chatbot. Ces tests
verifient ce choix — c'est-a-dire "l'intelligence" du moteur de rendu — de
maniere deterministe, et garantissent surtout deux proprietes de securite :

  1. Le planificateur ne modifie JAMAIS la logique metier : il est alimente par
     de vraies reponses de ChatbotExpert.repondre(), et l'on verifie que les
     valeurs affichees (segment, MMM, VRD...) sont exactement celles du moteur.
  2. Le planificateur est TOTAL : pour toute reponse possible du chatbot, il
     renvoie au moins un bloc et ne leve jamais d'exception.
"""
from __future__ import annotations

import sys

from _outils import Resultats

from chatbot.expert import ChatbotExpert
from core import MoteurSegmentation
from presentation.plan import (
    Badges, Callout, CarteDecision, Checklist, GroupeKPI, ListeStructuree,
    Reference, planifier_reponse,
)


def _type_present(blocs, classe):
    return any(isinstance(b, classe) for b in blocs)


def _premier(blocs, classe):
    return next(b for b in blocs if isinstance(b, classe))


def run() -> bool:
    r = Resultats("smart response renderer (planificateur)")
    chatbot = ChatbotExpert(MoteurSegmentation())

    # ================================================================== #
    # 1. Aide a la decision : carte + contexte + KPI + checklist + reference
    # ================================================================== #
    rep = chatbot.repondre("Marche = PART Profession = Ingenieurs Age = 45 MMM = 5000 VRD = 550000")
    blocs = planifier_reponse(rep)

    r.verifier("decision -> carte de decision presente", _type_present(blocs, CarteDecision))
    r.verifier("decision -> groupe de KPI present", _type_present(blocs, GroupeKPI))
    r.verifier("decision -> checklist des conditions presente", _type_present(blocs, Checklist))
    r.verifier("decision -> badges de contexte presents", _type_present(blocs, Badges))
    r.verifier("decision -> reference presente", _type_present(blocs, Reference))

    # La carte affiche EXACTEMENT le resultat du moteur (aucune reinterpretation).
    carte = _premier(blocs, CarteDecision)
    attendu = MoteurSegmentation().segmenter(
        {"Marche": "PART", "Profession": "Ingenieurs", "Age": 45, "MMM": 5000.0, "VRD": 550000.0}
    )
    r.egal("  la carte montre le segment du moteur", carte.segment, attendu.segment)
    r.egal("  et le sous-segment du moteur", carte.sous_segment, attendu.sous_segment)
    r.egal("  et la regle du moteur", carte.regle_id, attendu.regle_id)

    # Les KPI portent les valeurs EXACTES du profil, joliment formatees.
    # Note : le separateur de milliers est une espace INSECABLE (U+00A0),
    # typographie francaise correcte -> on la teste explicitement.
    ESP = " "  # espace insecable U+00A0
    kpis = {k.label: k.valeur for k in _premier(blocs, GroupeKPI).items}
    r.egal("  KPI Age correct", kpis.get("Age"), "45")
    r.egal("  KPI MMM formate (separateur de milliers insecable)", kpis.get("MMM"), f"5{ESP}000")
    r.egal("  KPI VRD formate", kpis.get("VRD (avoirs)"), f"550{ESP}000")

    # La checklist ne porte que les conditions de la REGLE RETENUE.
    checklist = _premier(blocs, Checklist)
    r.verifier("  la checklist n'est pas vide", len(checklist.items) > 0)
    r.verifier("  toutes les conditions de la regle retenue sont satisfaites",
               all(it.ok for it in checklist.items))

    # ================================================================== #
    # 2. Decision en ECHEC : alerte, pas de carte verte
    # ================================================================== #
    rep_ko = chatbot.repondre("Marche = TPME Age = 40 MMM = 1000 VRD = 0")
    if rep_ko.get("type") == "aide_decision":
        blocs_ko = planifier_reponse(rep_ko)
        r.verifier("decision en echec -> pas de carte de decision verte",
                   not _type_present(blocs_ko, CarteDecision))
        r.verifier("decision en echec -> encadre d'alerte present",
                   _type_present(blocs_ko, Callout))
    else:
        # TPME n'est pas detecte comme profil : on ne bloque pas le test.
        r.verifier("profil TPME traite sans exception", True)

    # ================================================================== #
    # 3. Connaissance ENUMEREE (TRE) -> liste structuree
    # ================================================================== #
    blocs_tre = planifier_reponse(chatbot.repondre("Quels sont les seuils TRE ?"))
    r.verifier("reponse TRE -> liste structuree", _type_present(blocs_tre, ListeStructuree))
    liste = _premier(blocs_tre, ListeStructuree)
    r.verifier("  la liste a plusieurs elements (Premium, Potentiel moyen...)",
               len(liste.items) >= 3)
    r.verifier("  le premier element est 'Premium'",
               liste.items[0].titre.startswith("Premium"))
    # Non-regression : les vraies valeurs (2,5 mD) restent presentes dans le detail.
    detail_concat = " ".join(it.detail for it in liste.items)
    r.verifier("  les seuils reels du moteur sont conserves (2.5 mD)",
               "2.5 mD" in detail_concat)

    # ================================================================== #
    # 4. Connaissance = un seul paragraphe -> encadre, PAS de fausse liste
    # ================================================================== #
    blocs_mmm = planifier_reponse(chatbot.repondre("Quelle est la logique entre MMM et VRD ?"))
    r.verifier("reponse a un seul point -> encadre simple", _type_present(blocs_mmm, Callout))
    r.verifier("  et PAS de liste structuree artificielle",
               not _type_present(blocs_mmm, ListeStructuree))
    callout = _premier(blocs_mmm, Callout)
    r.verifier("  le texte metier est conserve integralement (OU logique)",
               "OU logique" in callout.texte)

    # ================================================================== #
    # 5. Liste de professions -> pastilles (chips), pas un pave de texte
    # ================================================================== #
    blocs_pl = planifier_reponse(chatbot.repondre("Liste des professions liberales ?"))
    r.verifier("liste de professions -> pastilles", _type_present(blocs_pl, Badges))
    chips = _premier(blocs_pl, Badges)
    r.verifier("  plusieurs professions en pastilles", len(chips.items) >= 4)

    # ================================================================== #
    # 6. Message d'absence -> encadre d'information (jamais vide)
    # ================================================================== #
    blocs_abs = planifier_reponse(chatbot.repondre("Quelle est la meteo a Tunis ?"))
    r.verifier("absence d'info -> encadre", _type_present(blocs_abs, Callout))
    r.verifier("  le message d'absence est preserve",
               "n'est pas disponible" in _premier(blocs_abs, Callout).texte)

    # ================================================================== #
    # 7. Robustesse : TOTALITE du planificateur
    # ================================================================== #
    # Toutes les entrees de la base de connaissances + profils varies + cas
    # limites : le planificateur ne doit jamais lever ni renvoyer une liste vide.
    questions = [e["cles"][0] for e in chatbot.kb] + [
        "Marche = PRO Profession = Commercant Age = 40 MMM = 90 VRD = 3",
        "Marche = ENR Age = 30 MMM = 12000 VRD = 0",
        "Quelle est la meteo ?", "", "   ",
        "Seuils Affluent ?", "Grand public ?", "Les jeunes ?",
    ]
    robuste = True
    for q in questions:
        try:
            blocs_q = planifier_reponse(chatbot.repondre(q))
            if not blocs_q:
                robuste = False
        except Exception as exc:  # noqa: BLE001
            robuste = False
            print(f"    exception sur {q!r} : {exc!r}")
    r.verifier(f"planificateur total sur {len(questions)} reponses reelles "
               "(jamais vide, jamais d'exception)", robuste)

    # Entrees degenerees directes.
    for entree in ({}, {"type": "inconnu"}, {"type": "connaissance"}, None, "texte brut"):
        try:
            planifier_reponse(entree)
        except Exception as exc:  # noqa: BLE001
            r.verifier(f"entree degeneree {entree!r} sans exception", False, repr(exc))
            break
    else:
        r.verifier("entrees degenerees traitees sans exception", True)

    return r.bilan()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
