"""
Analyse de la structure d'un portefeuille client segmente.

Repond a une question metier : « Comment se structure le portefeuille PBD, et
ou se concentre la valeur ? » Produit des indicateurs chiffres (repartition par
segment et marche, concentration des avoirs, part de valeur / de potentiel) et
en derive des recommandations, generees a partir des chiffres eux-memes (jamais
codees en dur).

Lecture seule : consomme les segments deja produits par le moteur ; ne segmente
pas, ne modifie rien.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

# Regroupements de segments par enjeu commercial.
SEGMENTS_VALEUR = {"Haut de Gamme", "Premium"}          # forte valeur actuelle
SEGMENTS_POTENTIEL = {"Les Jeunes"}                      # potentiel futur
SEGMENTS_MASSE = {"Grand Public", "Faible potentiel"}   # marche de masse


def _pct(part: float) -> float:
    return float(round(100 * part, 1))


def _concentration_avoirs(vrd: pd.Series) -> dict[str, float]:
    """Mesures classiques de concentration des avoirs (VRD) :
      - part detenue par le decile / quintile superieur (effet Pareto) ;
      - indice de Gini (0 = egalite parfaite, 1 = concentration maximale).
    Ces indicateurs sont robustes et independants de la segmentation."""
    valeurs = np.sort(vrd.to_numpy(dtype=float))
    n = len(valeurs)
    total = valeurs.sum()
    if n == 0 or total <= 0:
        return {"top10": 0.0, "top20": 0.0, "gini": 0.0}
    top10 = valeurs[int(0.9 * n):].sum() / total
    top20 = valeurs[int(0.8 * n):].sum() / total
    cumul = np.cumsum(valeurs)
    gini = (n + 1 - 2 * (cumul.sum() / cumul[-1])) / n
    return {"top10": _pct(top10), "top20": _pct(top20), "gini": float(round(gini, 3))}


def analyser(portefeuille: pd.DataFrame) -> dict[str, Any]:
    """Calcule les indicateurs de structure du portefeuille. Renvoie un
    dictionnaire de resultats + une liste de constats et de recommandations."""
    n = len(portefeuille)
    seg = portefeuille["Segment"]

    # --- Repartitions ---------------------------------------------------
    repartition_segment = {k: _pct(v) for k, v in seg.value_counts(normalize=True).items()}
    mix_marche = {k: _pct(v) for k, v in portefeuille["Marche"].value_counts(normalize=True).items()}

    croise = pd.crosstab(portefeuille["Marche"], seg, normalize="index") * 100
    croise_marche_segment = {m: {s: round(croise.loc[m, s], 1) for s in croise.columns}
                             for m in croise.index}

    # --- Parts strategiques ---------------------------------------------
    part_valeur = seg.isin(SEGMENTS_VALEUR).mean()
    part_potentiel = seg.isin(SEGMENTS_POTENTIEL).mean()
    part_masse = seg.isin(SEGMENTS_MASSE).mean()

    # --- Concentration des avoirs -----------------------------------------
    # Deux angles complementaires :
    #  1) concentration PURE (Pareto / Gini) : part des avoirs detenue par le
    #     decile superieur, independamment de la segmentation ;
    #  2) part des avoirs detenue par les segments de VALEUR (Haut de Gamme /
    #     Premium), qui peut differer car ces segments incluent des clients
    #     qualifies par la PROFESSION (a potentiel), aux encours modestes.
    concentration = _concentration_avoirs(portefeuille["VRD"])
    vrd_total = float(portefeuille["VRD"].sum())
    vrd_valeur = float(portefeuille.loc[seg.isin(SEGMENTS_VALEUR), "VRD"].sum())
    part_avoirs_valeur = _pct((vrd_valeur / vrd_total) if vrd_total > 0 else 0.0)

    # --- Par marche : segment dominant + part de valeur -----------------
    par_marche = {}
    for marche, groupe in portefeuille.groupby("Marche"):
        vc = groupe["Segment"].value_counts(normalize=True)
        par_marche[marche] = {
            "effectif": int(len(groupe)),
            "segment_dominant": vc.index[0],
            "part_dominant": _pct(vc.iloc[0]),
            "part_valeur": _pct(groupe["Segment"].isin(SEGMENTS_VALEUR).mean()),
        }

    # --- Superposition anomalies ML (qualite des donnees) ---------------
    taux_anomalies = None
    if "ML_Anomalie" in portefeuille and portefeuille["ML_Anomalie"].notna().any():
        taux_anomalies = float(portefeuille["ML_Anomalie"].fillna(False).astype(bool).mean())

    resultats: dict[str, Any] = {
        "n_clients": n,
        "mix_marche": mix_marche,
        "repartition_segment": repartition_segment,
        "croise_marche_segment": croise_marche_segment,
        "part_valeur": _pct(part_valeur),
        "part_potentiel": _pct(part_potentiel),
        "part_masse": _pct(part_masse),
        "concentration_top10": concentration["top10"],
        "concentration_top20": concentration["top20"],
        "gini_avoirs": concentration["gini"],
        "part_avoirs_segments_valeur": part_avoirs_valeur,
        "par_marche": par_marche,
        "taux_anomalies": _pct(taux_anomalies) if taux_anomalies is not None else None,
    }
    resultats["constats"] = _constats(resultats)
    resultats["recommandations"] = _recommandations(resultats)
    return resultats


def _constats(r: dict) -> list[str]:
    """Constats chiffres, derives des indicateurs."""
    c = [
        f"Le portefeuille compte {r['n_clients']} clients, dont "
        f"{r['mix_marche'].get('PART', 0)} % sur le marche des Particuliers.",
        f"Les avoirs sont fortement concentres : le decile superieur des clients "
        f"detient {r['concentration_top10']} % des encours (top 20 % : "
        f"{r['concentration_top20']} %), pour un indice de Gini de {r['gini_avoirs']}.",
        f"La clientele de forte valeur au sens des segments (Haut de Gamme / Premium) "
        f"represente {r['part_valeur']} % des clients et detient "
        f"{r['part_avoirs_segments_valeur']} % des avoirs -- ecart avec le decile "
        "superieur qui s'explique par les clients qualifies par la profession (a "
        "potentiel) plutot que par les montants.",
        f"Le marche de masse (Grand Public / Faible potentiel) represente "
        f"{r['part_masse']} % des clients.",
        f"Les Jeunes representent {r['part_potentiel']} % du portefeuille "
        "(potentiel de developpement futur).",
    ]
    # Marche le plus dote en clientele de valeur.
    if r["par_marche"]:
        meilleur = max(r["par_marche"].items(), key=lambda kv: kv[1]["part_valeur"])
        c.append(f"Le marche {meilleur[0]} est le plus riche en clientele de valeur "
                 f"({meilleur[1]['part_valeur']} % de Haut de Gamme / Premium).")
    return c


def _recommandations(r: dict) -> list[str]:
    """Recommandations metier, declenchees par des seuils sur les indicateurs.
    Chaque recommandation est justifiee par un chiffre du portefeuille."""
    reco: list[str] = []

    if r["concentration_top10"] >= 30:
        reco.append(
            f"Forte concentration des avoirs (le decile superieur detient "
            f"{r['concentration_top10']} % des encours, Gini {r['gini_avoirs']}) : la "
            "priorite est de securiser et fideliser cette clientele patrimoniale par une "
            "gestion dediee, sa perte ayant un impact disproportionne sur les encours.")

    if r["part_masse"] >= 35:
        reco.append(
            f"Marche de masse important ({r['part_masse']} %) : levier de montee en gamme "
            "via des produits d'epargne et de bancarisation, pour faire progresser une "
            "partie de ces clients vers la Classe Moyenne.")

    if r["part_potentiel"] >= 15:
        reco.append(
            f"Les Jeunes representent {r['part_potentiel']} % : une strategie de "
            "fidelisation precoce (offres d'equipement, accompagnement) permettrait de les "
            "convertir en clients Affluent a mesure de la hausse de leurs revenus.")

    # Marches TRE/ENR sous-developpes (majoritairement faible potentiel).
    tre_enr = {m: v for m, v in r["par_marche"].items() if m in ("TRE", "ENR")}
    sous_dev = [(m, v["part_dominant"]) for m, v in tre_enr.items()
                if v["segment_dominant"] in ("Faible potentiel", "Potentiel moyen")
                and v["part_dominant"] >= 60]
    if sous_dev:
        detail = ", ".join(f"{m} {p:g} %" for m, p in sorted(sous_dev))
        reco.append(
            f"Marches TRE/ENR majoritairement en faible potentiel ({detail} de faible "
            "potentiel) : clientele expatriee aux encours modestes. Opportunite de "
            "developpement (produits de transfert, epargne rapatriee) ou choix assume de "
            "ne pas y investir -- a arbitrer.")

    if r["taux_anomalies"] is not None and r["taux_anomalies"] >= 3:
        reco.append(
            f"Le module de detection signale {r['taux_anomalies']} % de profils atypiques : "
            "un controle qualite des donnees d'entree (saisies incoherentes) fiabiliserait "
            "la segmentation et les analyses qui en decoulent.")

    if not reco:  # garde-fou : jamais de liste vide
        reco.append("Structure de portefeuille equilibree : aucun desequilibre majeur "
                    "detecte sur les indicateurs analyses.")
    return reco
