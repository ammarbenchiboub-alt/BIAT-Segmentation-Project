"""
Jeu d'evaluation ETIQUETE pour le module de detection d'anomalies.

Le modele est non supervise et entraine sur des donnees SIMULEES : il n'existe
donc, dans le projet, aucune anomalie de reference permettant de le noter. Ce
module construit un tel jeu de reference, de maniere transparente et
reproductible :

    - des profils NORMAUX tenus a l'ecart : tires de la MEME distribution
      plausible que l'entrainement, mais avec une graine DIFFERENTE (pas de
      fuite : le modele n'a jamais vu ces profils) ;
    - des ANOMALIES injectees, ETIQUETEES par type : chaque profil anormal est
      construit deliberement pour representer une erreur de saisie ou une
      combinaison implausible identifiable par un humain.

Ce jeu definit donc explicitement ce que « anomalie » signifie dans
l'evaluation. C'est la demarche standard pour evaluer une detection non
supervisee en l'absence de labels reels : on mesure la capacite du modele a
retrouver des anomalies CONNUES, en enoncant clairement lesquelles.

Ce module ne MODIFIE jamais le modele : il ne fait que produire des donnees.
Il n'importe pas le moteur de segmentation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.ml_anomaly import _generer_donnees_entrainement

# Graine de l'evaluation, VOLONTAIREMENT differente de celle de l'entrainement
# (42) : les profils normaux d'evaluation sont ainsi tenus a l'ecart.
GRAINE_EVALUATION = 2024

# Champs d'un profil (memes que ceux vus par le modele).
CHAMPS_PROFIL = ["Marche", "Age", "MMM", "VRD", "Profession", "Nationalite", "Residence"]

# Description lisible de chaque famille d'anomalie injectee.
TYPES_ANOMALIES = {
    "montant_extreme": "Montants MMM/VRD hors de toute echelle realiste (erreur de saisie de grande ampleur).",
    "age_enfant_marche_adulte": "Age d'enfant (6-15 ans) sur un marche reserve aux adultes (PRO/TRE/ENR).",
    "etudiant_age_incoherent": "Profession 'Etudiant' associee a un age eleve (45-70 ans).",
    "ENR_nationalite_tunisienne": "Marche ENR (Etranger Non Resident) avec Nationalite = Tunisienne (contradiction).",
    "TRE_resident_oui": "Marche TRE (Resident a l'Etranger) avec Residence = Oui (contradiction).",
}


def construire_jeu_reference(n_normaux_par_marche: int = 500,
                             n_par_anomalie: int = 120) -> pd.DataFrame:
    """Construit le jeu d'evaluation etiquete.

    Renvoie un DataFrame avec les champs de profil + `label` (0 = normal,
    1 = anomalie) + `type` (famille d'anomalie, ou 'normal').

    Les anomalies « categorielles » (nationalite / residence contradictoires)
    recoivent des montants NORMAUX : seule la variable categorielle est fausse.
    Cela evite qu'un detecteur fonde sur les montants ne les attrape « par
    accident », et permet une comparaison loyale entre modele et baseline.
    """
    rng = np.random.default_rng(GRAINE_EVALUATION)

    normaux = _generer_donnees_entrainement(
        n_par_marche=n_normaux_par_marche, graine=GRAINE_EVALUATION
    )
    normaux = normaux.assign(label=0, type="normal")

    lignes: list[dict] = []

    def ajouter(marche, age, mmm, vrd, profession, nationalite, residence, type_):
        lignes.append({
            "Marche": marche, "Age": int(age), "MMM": float(mmm), "VRD": float(vrd),
            "Profession": profession, "Nationalite": nationalite,
            "Residence": residence, "label": 1, "type": type_,
        })

    for _ in range(n_par_anomalie):
        ajouter(rng.choice(["PART", "PRO", "TRE", "ENR"]), rng.integers(30, 60),
                rng.integers(2_000_000, 50_000_000), rng.integers(5_000_000, 80_000_000),
                "Autre", "Tunisienne", "Oui", "montant_extreme")

    for _ in range(n_par_anomalie):
        ajouter(rng.choice(["PRO", "TRE", "ENR"]), rng.integers(6, 16),
                rng.lognormal(6.5, 1.3), rng.lognormal(9.5, 1.5),
                "Autre", "Tunisienne", "Oui", "age_enfant_marche_adulte")

    for _ in range(n_par_anomalie):
        ajouter("PART", rng.integers(45, 70),
                rng.lognormal(6.5, 1.3), rng.integers(200_000, 800_000),
                "Etudiant", "Tunisienne", "Oui", "etudiant_age_incoherent")

    # --- Anomalies purement categorielles : montants NORMAUX du marche ---
    for _ in range(n_par_anomalie):
        ajouter("ENR", rng.integers(30, 60),
                rng.lognormal(7.5, 1.4), rng.lognormal(10.0, 1.5),
                "Autre", "Tunisienne", "Non", "ENR_nationalite_tunisienne")

    for _ in range(n_par_anomalie):
        ajouter("TRE", rng.integers(30, 60),
                rng.lognormal(6.8, 1.4), rng.lognormal(9.8, 1.5),
                "Autre", "Tunisienne", "Oui", "TRE_resident_oui")

    anomalies = pd.DataFrame(lignes)
    return pd.concat([normaux, anomalies], ignore_index=True)
