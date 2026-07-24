"""
Construction d'un portefeuille client REPRESENTATIF, segmente par le moteur.

Il n'existe aucune donnee client reelle BIAT dans le projet. Ce module genere
donc un portefeuille SIMULE mais plausible, uniquement destine a l'analyse de
structure. Les profils sont ensuite segmentes par le MOTEUR OFFICIEL (lecture
seule) : l'analyse porte donc sur des decisions reelles du moteur, appliquees a
une population representative.

Hypotheses de generation, explicites et assumees (a remplacer par des donnees
reelles des qu'elles seront disponibles) :
  - Mix de marche calque sur une banque de detail tunisienne (PART majoritaire).
  - Professions ponderees de maniere realiste : la majorite des clients sont
    des salaries / "Autre" ; les professions a potentiel (medecins, ingenieurs,
    magistrats...) sont une minorite -- sans quoi la part de Haut de Gamme
    serait irrealiste (ces professions qualifient HG independamment du montant).
  - Montants MMM/VRD tires de lois log-normales calibrees pour produire une
    pyramide de valeur credible (masse en Grand Public / Classe Moyenne,
    minorite en Haut de Gamme).

Ce module ne MODIFIE ni le moteur, ni les regles, ni aucun resultat : il ne
fait que LEUR SOUMETTRE des profils et lire le segment renvoye.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core import MoteurSegmentation

GRAINE_PORTEFEUILLE = 1234
N_DEFAUT = 8000

# Mix de marche (HYPOTHESE plausible, non issue de donnees reelles).
MIX_MARCHE = {"PART": 0.68, "PRO": 0.18, "TRE": 0.09, "ENR": 0.05}

# Parametres par marche : (mmm_mean, mmm_sigma, vrd_mean, vrd_sigma, age_min, age_max)
# des lois log-normales (mean/sigma en echelle log). Calibres pour une
# distribution de segments credible (voir docstring).
_PARAMS = {
    "PART": (5.9, 0.90, 8.4, 1.00, 18, 85),
    "PRO":  (6.6, 1.00, 8.9, 1.10, 24, 75),
    "TRE":  (5.9, 0.95, 8.5, 1.00, 22, 75),
    "ENR":  (6.4, 0.95, 8.7, 1.00, 25, 78),
}

# Professions ponderees (realistes) : majorite "Autre"/salaries, potentiel rare.
_PROFESSIONS = {
    "PART": (["Autre", "Commercant", "Etudiant", "Ingenieurs", "Medecins generalistes", "Magistrats"],
             [0.70, 0.12, 0.08, 0.05, 0.03, 0.02]),
    "PRO":  (["Commercant", "Artisan", "Autre", "Avocats", "Ingenieurs", "Experts-comptables"],
             [0.42, 0.28, 0.15, 0.06, 0.05, 0.04]),
    "TRE":  (["Autre", "Commercant", "Ingenieurs", "Medecins specialistes"],
             [0.80, 0.12, 0.05, 0.03]),
    "ENR":  (["Autre", "Commercant", "Ingenieurs", "Medecins generalistes"],
             [0.82, 0.11, 0.04, 0.03]),
}

_NAT_RES = {
    "PART": (["Tunisienne"] * 95 + ["Autre"] * 5, ["Oui"] * 96 + ["Non"] * 4),
    "PRO":  (["Tunisienne"] * 97 + ["Autre"] * 3, ["Oui"] * 96 + ["Non"] * 4),
    "TRE":  (["Tunisienne"], ["Non"] * 95 + ["Oui"] * 5),
    "ENR":  (["Autre"], ["Non"] * 95 + ["Oui"] * 5),
}

# Part d'enfants (< 19 ans) au sein du marche PART.
_PART_ENFANTS = 0.10


def generer_profils(n: int = N_DEFAUT, graine: int = GRAINE_PORTEFEUILLE) -> pd.DataFrame:
    """Genere `n` profils clients representatifs (non segmentes). Deterministe."""
    rng = np.random.default_rng(graine)
    lignes: list[dict] = []
    for marche, part in MIX_MARCHE.items():
        n_marche = int(round(n * part))
        mmm_m, mmm_s, vrd_m, vrd_s, age_lo, age_hi = _PARAMS[marche]
        professions, poids = _PROFESSIONS[marche]
        nationalites, residences = _NAT_RES[marche]
        for _ in range(n_marche):
            if marche == "PART" and rng.random() < _PART_ENFANTS:
                age = int(rng.integers(6, 19))
            else:
                age = int(rng.integers(age_lo, age_hi))
            lignes.append({
                "Marche": marche,
                "Profession": str(rng.choice(professions, p=poids)),
                "Age": age,
                "MMM": float(max(0.0, rng.lognormal(mmm_m, mmm_s))),
                "VRD": float(max(0.0, rng.lognormal(vrd_m, vrd_s))),
                "Nationalite": str(rng.choice(nationalites)),
                "Residence": str(rng.choice(residences)),
            })
    return pd.DataFrame(lignes)


def segmenter_portefeuille(profils: pd.DataFrame,
                           moteur: MoteurSegmentation | None = None) -> pd.DataFrame:
    """Segmente chaque profil via le MOTEUR OFFICIEL et ajoute les colonnes
    Segment / Sous_segment / Regle. Lecture seule : le moteur n'est pas modifie."""
    moteur = moteur or MoteurSegmentation()
    resultats = [moteur.segmenter(p) for p in profils.to_dict("records")]
    df = profils.copy()
    df["Segment"] = [r.segment or "-" for r in resultats]
    df["Sous_segment"] = [r.sous_segment or "-" for r in resultats]
    df["Regle"] = [r.regle_id or "-" for r in resultats]
    return df


def construire_portefeuille(n: int = N_DEFAUT, graine: int = GRAINE_PORTEFEUILLE,
                            moteur: MoteurSegmentation | None = None) -> pd.DataFrame:
    """Portefeuille representatif complet : profils generes puis segmentes."""
    return segmenter_portefeuille(generer_profils(n, graine), moteur)
