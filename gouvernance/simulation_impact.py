"""
Simulation d'impact ("dry-run") d'un changement de regles de segmentation.

Avant de proposer ou de confirmer un changement de seuils/professions, permet
de mesurer son effet sur de vrais profils deja segmentes (issus du journal
d'audit) : combien de clients changeraient de segment, et vers quoi.

Ce module est en LECTURE SEULE : il ne modifie jamais
regles_segmentation.json ni le journal d'audit, il se contente de rejouer des
profils existants a travers un jeu de regles candidat (jamais encore ecrit
sur disque) via le moteur officiel (core.engine), pour comparaison.
"""
from __future__ import annotations

import pandas as pd

from core import MoteurSegmentation

_CHAMPS_PROFIL = ["Marche", "Profession", "Age", "MMM", "VRD", "Nationalite", "Residence",
                   "EpargnantDeposantExclusif"]


def simuler_impact(regles_proposees: dict, profils: list[dict]) -> pd.DataFrame:
    """Rejoue une liste de profils a travers les regles ACTUELLES (chargees
    depuis le fichier officiel) et les regles PROPOSEES (en memoire
    uniquement), et renvoie un DataFrame comparant les deux resultats."""
    moteur_actuel = MoteurSegmentation()
    moteur_propose = MoteurSegmentation(regles=regles_proposees)

    lignes = []
    for profil in profils:
        entree = {champ: profil.get(champ) for champ in _CHAMPS_PROFIL}
        entree["EpargnantDeposantExclusif"] = bool(entree.get("EpargnantDeposantExclusif") or False)
        if entree.get("Marche") is None or entree.get("Age") is None:
            continue
        try:
            res_actuel = moteur_actuel.segmenter(entree)
            res_propose = moteur_propose.segmenter(entree)
        except Exception:  # noqa: BLE001 - profil non exploitable, ignore silencieusement
            continue
        changement = (res_actuel.segment, res_actuel.sous_segment) != (res_propose.segment, res_propose.sous_segment)
        lignes.append({
            "Marche": entree["Marche"], "Profession": entree["Profession"], "Age": entree["Age"],
            "MMM": entree["MMM"], "VRD": entree["VRD"],
            "Segment_actuel": res_actuel.segment or "-",
            "Sous_segment_actuel": res_actuel.sous_segment or "-",
            "Segment_propose": res_propose.segment or "-",
            "Sous_segment_propose": res_propose.sous_segment or "-",
            "Changement": changement,
        })
    return pd.DataFrame(lignes)
