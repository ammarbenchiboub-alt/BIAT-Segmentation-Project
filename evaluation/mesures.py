"""
Mesures d'evaluation du detecteur d'anomalies (Isolation Forest).

Calcule, sur le jeu de reference etiquete (evaluation.jeu_reference), des
metriques standard et une comparaison a une baseline simple. Le detecteur est
UTILISE tel quel (modele livre charge depuis le disque) : il n'est ni
reentraine ni modifie.

Metriques retenues et pourquoi
------------------------------
  - ROC-AUC / PR-AUC : mesurent la qualite du CLASSEMENT (ranking) des profils
    par score d'anomalie, INDEPENDAMMENT du seuil. C'est la mesure la plus
    honnete de la capacite discriminante du modele, car elle ne depend pas du
    choix de `contamination`.
  - Precision / Rappel / F1 : au seuil de decision REEL du modele (celui fixe
    par contamination=0.06), pour refleter le comportement en production.
  - Taux de fausses alertes sur les NORMAUX : c'est l'interpretation concrete de
    `contamination` -- la fraction de clients normaux qui declencheraient une
    alerte a tort.
  - Rappel par TYPE d'anomalie : montre les forces et faiblesses du modele
    selon la nature de l'erreur (montant, age, incoherence categorielle).
  - Courbe operationnelle : rappel obtenu pour differents budgets de fausses
    alertes, pour situer et justifier le choix de contamination.

La baseline (z-score robuste par marche sur MMM/VRD + bornes d'age) represente
« ce qu'on obtiendrait avec quelques regles simples ». La comparaison repond a
la question du jury : le modele apporte-t-il quelque chose de plus ?
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score, confusion_matrix, f1_score, precision_score,
    recall_score, roc_auc_score,
)

from core.ml_anomaly import DetecteurAnomalies, _generer_donnees_entrainement

from .jeu_reference import construire_jeu_reference

# Budgets de fausses alertes explores pour la courbe operationnelle.
BUDGETS_FAUSSES_ALERTES = [0.02, 0.04, 0.06, 0.08, 0.10, 0.15]

# Seuil de la baseline (z-score robuste). Au-dela, la ligne est jugee anormale.
_SEUIL_BASELINE = 3.5


def _metriques(y: np.ndarray, score_anomalie: np.ndarray, drapeau: np.ndarray) -> dict:
    """Metriques pour un scoreur donne. `score_anomalie` : plus haut = plus
    anormal (pour AUC). `drapeau` : decision binaire 0/1 (pour precision/rappel)."""
    tn, fp, fn, tp = confusion_matrix(y, drapeau).ravel()
    return {
        "roc_auc": float(roc_auc_score(y, score_anomalie)),
        "pr_auc": float(average_precision_score(y, score_anomalie)),
        "precision": float(precision_score(y, drapeau, zero_division=0)),
        "rappel": float(recall_score(y, drapeau, zero_division=0)),
        "f1": float(f1_score(y, drapeau, zero_division=0)),
        "matrice": {"vn": int(tn), "fp": int(fp), "fn": int(fn), "vp": int(tp)},
    }


def _scoreur_baseline(jeu: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Baseline transparente : z-score robuste (mediane / MAD) par marche sur
    MMM et VRD, plus bornes d'age plausibles. Calibree sur la meme distribution
    de reference que l'entrainement du modele."""
    ref = _generer_donnees_entrainement(n_par_marche=1500, graine=42)
    stats: dict = {}
    for marche, groupe in ref.groupby("Marche"):
        stats[marche] = {}
        for champ in ("MMM", "VRD"):
            mediane = groupe[champ].median()
            mad = (groupe[champ] - mediane).abs().median() or 1.0
            stats[marche][champ] = (mediane, mad)

    scores = np.empty(len(jeu))
    for i, (_, p) in enumerate(jeu.iterrows()):
        s = 0.0
        for champ in ("MMM", "VRD"):
            mediane, mad = stats[p["Marche"]][champ]
            s = max(s, abs(0.6745 * (p[champ] - mediane) / mad))
        if p["Age"] < 18 or p["Age"] > 90:
            s = max(s, 10.0)
        scores[i] = s
    return scores, (scores > _SEUIL_BASELINE).astype(int)


def evaluer(detecteur: DetecteurAnomalies | None = None) -> dict[str, Any]:
    """Evalue le modele LIVRE sur le jeu de reference et renvoie un dictionnaire
    de resultats (metriques modele, baseline, rappel par type, interpretation de
    contamination, courbe operationnelle). Deterministe (tout est graine)."""
    detecteur = detecteur or DetecteurAnomalies.charger_ou_entrainer()
    jeu = construire_jeu_reference()
    y = jeu["label"].to_numpy()
    est_normal = (jeu["type"] == "normal").to_numpy()
    profils = jeu[["Marche", "Age", "MMM", "VRD", "Profession", "Nationalite", "Residence"]].to_dict("records")

    # --- Isolation Forest (modele livre) --------------------------------
    scores_bruts = detecteur._scores_bruts(profils)      # >0 normal, <0 anomalie
    score_if = -np.asarray(scores_bruts)                 # plus haut = plus anormal
    drapeau_if = (np.asarray(scores_bruts) < 0).astype(int)
    m_if = _metriques(y, score_if, drapeau_if)
    m_if["fausses_alertes_normaux"] = float(drapeau_if[est_normal].mean())

    # --- Baseline (regles simples) --------------------------------------
    score_base, drapeau_base = _scoreur_baseline(jeu)
    m_base = _metriques(y, score_base, drapeau_base)
    m_base["fausses_alertes_normaux"] = float(drapeau_base[est_normal].mean())

    # --- Rappel par type d'anomalie -------------------------------------
    rappel_type_if, rappel_type_base = {}, {}
    for type_ in jeu.loc[jeu["label"] == 1, "type"].unique():
        masque = (jeu["type"] == type_).to_numpy()
        rappel_type_if[type_] = float(drapeau_if[masque].mean())
        rappel_type_base[type_] = float(drapeau_base[masque].mean())

    # --- Courbe operationnelle : budget de fausses alertes -> rappel -----
    # Le seuil est fixe sur la distribution des scores des NORMAUX : un budget
    # de b% signifie « on accepte b% de fausses alertes sur les clients
    # normaux », et l'on mesure le rappel obtenu sur les anomalies.
    scores_normaux = score_if[est_normal]
    est_anomalie = (y == 1)
    courbe = []
    for budget in BUDGETS_FAUSSES_ALERTES:
        seuil = float(np.quantile(scores_normaux, 1 - budget))
        detecte = score_if >= seuil
        courbe.append({
            "budget_fausses_alertes": budget,
            "rappel": float(detecte[est_anomalie].mean()),
            "fausses_alertes_reelles": float(detecte[est_normal].mean()),
        })

    return {
        "n_normaux": int(est_normal.sum()),
        "n_anomalies": int((~est_normal).sum()),
        "contamination_modele": 0.06,
        "isolation_forest": m_if,
        "baseline": m_base,
        "rappel_par_type_if": rappel_type_if,
        "rappel_par_type_baseline": rappel_type_base,
        "courbe_operationnelle": courbe,
        "metadonnees_modele": dict(detecteur.metadonnees),
    }
