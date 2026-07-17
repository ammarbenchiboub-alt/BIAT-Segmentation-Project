"""
MODULE MACHINE LEARNING - DETECTION D'ANOMALIES SUR LES PROFILS CLIENTS
========================================================================

Ce module est une fonctionnalite COMPLEMENTAIRE et INDEPENDANTE du moteur de
segmentation officiel (core.engine). Il NE remplace JAMAIS, NE modifie JAMAIS
et NE recalcule JAMAIS un segment ou un sous-segment.

Le moteur de segmentation (core.engine, config/regles_segmentation.json) reste
l'UNIQUE source officielle de decision. Ce module se contente d'analyser, a
posteriori et de maniere purement statistique, la coherence d'un profil client
deja segmente par le moteur, afin d'assister le conseiller (aide a la
decision). Il agit uniquement comme un assistant intelligent supplementaire :
un client n'est jamais reclasse par ce module.

Sens de la dependance (volontairement a sens unique) :
    - Ce module s'execute FONCTIONNELLEMENT apres le moteur de segmentation
      (il analyse un profil deja segmente).
    - Il n'importe cependant RIEN de core.engine : aucune ligne de code de ce
      fichier ne depend du moteur, afin de garantir qu'une evolution ou une
      erreur de ce module ne puisse jamais, structurellement, impacter le
      moteur de segmentation.
    - L'inverse (core.engine impose ce module) n'existe pas et ne doit jamais
      etre introduit : core/engine.py ne doit JAMAIS importer core/ml_anomaly.py.

Algorithme : Isolation Forest (scikit-learn), non supervise.
Le modele est entraine sur un jeu de profils SIMULES mais plausibles,
construits a partir des ordres de grandeur de la Note BIAT 2023-06 (faute de
disposer d'un historique reel de clients BIAT), puis sauvegarde sur disque
(core/ml_model/anomaly_pipeline.joblib) afin d'eviter un reentrainement a
chaque lancement de l'application.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
from joblib import dump, load
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

CHAMPS_NUMERIQUES = ["Age", "MMM", "VRD"]
CHAMPS_CATEGORIELS = ["Marche", "Profession", "Nationalite", "Residence"]
CHAMPS_MODELE = CHAMPS_NUMERIQUES + CHAMPS_CATEGORIELS

MARCHES_CONNUS = ("PART", "PRO", "TRE", "ENR")

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_MODELE = os.path.join(_BASE_DIR, "core", "ml_model")
CHEMIN_MODELE = os.path.join(DOSSIER_MODELE, "anomaly_pipeline.joblib")

# Seuils de niveau, exprimes en score de confiance (%, 100 = parfaitement
# normal / typique par rapport aux profils simules d'entrainement).
SEUIL_NORMAL = 85
SEUIL_ATYPIQUE = 55

EMOJI_NIVEAU = {"Normal": "✅", "Atypique": "⚠️", "Incoherent": "❌"}

# Coherence indicative marche <-> residence / nationalite, utilisee UNIQUEMENT
# pour generer des explications lisibles (n'influence pas le score du modele,
# qui est purement statistique / issu de l'Isolation Forest). Ces valeurs
# reprennent les memes attentes indicatives que assistant/ai_assistant.py,
# sans creer de dependance de code vers ce module.
_COHERENCE_INDICATIVE = {
    "PART": {"Residence": "Oui"},
    "PRO": {"Residence": "Oui"},
    "TRE": {"Residence": "Non", "Nationalite": "Tunisienne"},
    "ENR": {"Residence": "Non", "Nationalite": "Autre"},
}

_PROFESSIONS_COURANTES = [
    "Autre", "Etudiant", "Commercant", "Artisan", "Salarie", "Ingenieurs",
    "Medecins generalistes", "Avocats", "Experts-comptables",
]

# Professions "a potentiel" / liberales (annexes 4 et 5 de la note), utilisees
# uniquement pour regrouper la profession en une categorie large avant de
# l'envoyer au modele (voir _bucket_profession). Un one-hot encoding sur des
# dizaines de professions distinctes, chacune peu representee, degraderait la
# stabilite d'Isolation Forest (dimensions sparses = bruit) ; regrouper en
# quelques categories larges rend le modele beaucoup plus robuste, sans rien
# changer au moteur de segmentation (qui, lui, continue d'utiliser la liste
# exhaustive et exacte des professions).
_PROFESSIONS_A_POTENTIEL_OU_LIBERALES = {
    "medecins generalistes", "medecins dentistes", "medecins veterinaires", "medecins specialistes",
    "pharmaciens", "biologistes et assimiles", "opticiens-lunetiers", "avocats", "experts-comptables",
    "ingenieurs", "architectes et urbanistes", "magistrats", "enseignants universitaires",
    "chefs de mission diplomatique et assimiles", "pilotes et officiers de pont",
    "professions paramedicales", "huissiers de justice, notaires, experts judiciaires et assimiles",
    "conseillers et consultants", "transitaires et commissionnaires",
    "medecins (fonction publique et assimiles en cas de resident)",
    "medecins de la fonction publique et assimiles",
    "hauts fonctionnaires de l'administration publique (en cas de resident)",
}


def _bucket_profession(profession) -> str:
    """Regroupe une profession en une categorie large (utilisee uniquement par
    le modele ML, jamais par le moteur de segmentation)."""
    p = str(profession or "").strip()
    if not p:
        return "Non renseigne"
    pl = p.lower()
    if pl == "autre":
        return "Autre"
    if pl == "etudiant":
        return "Etudiant"
    if pl in ("commercant", "artisan"):
        return "Commercant/Artisan"
    if pl in _PROFESSIONS_A_POTENTIEL_OU_LIBERALES:
        return "Profession a potentiel / liberale"
    return "Salarie / autre profession"


# --------------------------------------------------------------------------- #
# Generation de donnees d'entrainement simulees
# --------------------------------------------------------------------------- #

def _generer_donnees_entrainement(n_par_marche: int = 1500, graine: int = 42) -> pd.DataFrame:
    """Genere un jeu de profils simules mais plausibles, par marche.

    Faute d'historique reel de clients BIAT, ce jeu sert de reference du
    "comportement normal" pour l'apprentissage non supervise. Les ordres de
    grandeur (age, MMM, VRD) sont calques sur les paliers de la Note 2023-06,
    et la coherence marche / nationalite / residence reprend les regles
    indicatives deja utilisees par l'assistant IA (a titre de vraisemblance
    statistique uniquement ; ce module reste independant de tout autre code).
    """
    rng = np.random.default_rng(graine)
    lignes: list[dict] = []

    def _arrondir_realiste(valeur: float) -> float:
        """Une partie des montants generes est ramenee a des valeurs 'rondes'
        (0, ou multiples de 100/500/5000/50000 selon l'ordre de grandeur), pour
        refleter la facon dont un conseiller saisit reellement un montant (ex:
        5000, 15000, 550000). Sans cela, le modele n'apprend que des montants
        "au hasard" (ex: 4237,18 DT) et considere a tort les valeurs rondes,
        pourtant tres frequentes en pratique, comme statistiquement suspectes."""
        if valeur <= 0:
            return 0.0
        u = rng.random()
        if u < 0.05:
            return 0.0
        if u < 0.55:
            if valeur < 2000:
                pas = 100
            elif valeur < 20000:
                pas = 500
            elif valeur < 100000:
                pas = 5000
            else:
                pas = 50000
            return float(round(valeur / pas) * pas)
        return valeur

    def _ajouter(marche, age_fn, mmm_fn, vrd_fn, nationalite, residence, professions):
        for _ in range(n_par_marche):
            nat = nationalite() if callable(nationalite) else nationalite
            res = residence() if callable(residence) else residence
            lignes.append({
                "Marche": marche,
                "Age": int(age_fn()),
                "MMM": _arrondir_realiste(float(max(0, mmm_fn()))),
                "VRD": _arrondir_realiste(float(max(0, vrd_fn()))),
                "Profession": rng.choice(professions),
                "Nationalite": nat,
                "Residence": res,
            })

    # PART : population large (enfants, jeunes, adultes) ; Residence majoritairement "Oui"
    def _age_part():
        u = rng.random()
        if u < 0.12:
            return rng.integers(6, 19)
        if u < 0.28:
            return rng.integers(19, 31)
        return rng.integers(31, 85)

    _ajouter(
        "PART", _age_part,
        lambda: rng.lognormal(mean=6.5, sigma=1.3),
        lambda: rng.lognormal(mean=9.5, sigma=1.6),
        lambda: rng.choice(["Tunisienne"] * 95 + ["Autre"] * 5),
        lambda: rng.choice(["Oui"] * 96 + ["Non"] * 4),
        _PROFESSIONS_COURANTES + ["Magistrats", "Ingenieurs", "Etudiant"],
    )

    # PRO : adultes uniquement ; Residence majoritairement "Oui"
    _ajouter(
        "PRO", lambda: rng.integers(24, 75),
        lambda: rng.lognormal(mean=8.5, sigma=1.6),
        lambda: rng.lognormal(mean=10.2, sigma=1.7),
        lambda: rng.choice(["Tunisienne"] * 97 + ["Autre"] * 3),
        lambda: rng.choice(["Oui"] * 96 + ["Non"] * 4),
        ["Commercant", "Artisan", "Avocats", "Experts-comptables", "Ingenieurs", "Medecins generalistes", "Autre"],
    )

    # TRE : adultes, Tunisiens residant a l'etranger -> Residence majoritairement "Non"
    _ajouter(
        "TRE", lambda: rng.integers(22, 75),
        lambda: rng.lognormal(mean=6.8, sigma=1.4),
        lambda: rng.lognormal(mean=9.8, sigma=1.5),
        "Tunisienne",
        lambda: rng.choice(["Non"] * 95 + ["Oui"] * 5),
        _PROFESSIONS_COURANTES + ["Medecins specialistes", "Ingenieurs"],
    )

    # ENR : etrangers non-residents
    _ajouter(
        "ENR", lambda: rng.integers(25, 78),
        lambda: rng.lognormal(mean=7.5, sigma=1.4),
        lambda: rng.lognormal(mean=10.0, sigma=1.5),
        "Autre",
        lambda: rng.choice(["Non"] * 95 + ["Oui"] * 5),
        ["Autre", "Ingenieurs", "Medecins generalistes", "Commercant"],
    )

    return pd.DataFrame(lignes)


def _construire_pipeline() -> Pipeline:
    """Pretraitement (normalisation + encodage) suivi de l'Isolation Forest."""
    pretraitement = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), CHAMPS_NUMERIQUES),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CHAMPS_CATEGORIELS),
        ]
    )
    return Pipeline(steps=[
        ("pretraitement", pretraitement),
        ("modele", IsolationForest(n_estimators=200, contamination=0.06, random_state=42, n_jobs=-1)),
    ])


# --------------------------------------------------------------------------- #
# Detecteur d'anomalies
# --------------------------------------------------------------------------- #

class DetecteurAnomalies:
    """Detection d'anomalies / d'incoherences statistiques sur un profil client.

    ATTENTION : ce detecteur ne calcule et ne modifie JAMAIS de segment ni de
    sous-segment. C'est un module d'aide a la decision, purement statistique,
    qui s'execute APRES le moteur de segmentation officiel.
    """

    def __init__(self):
        self.pipeline: Pipeline | None = None
        self.scores_entrainement: np.ndarray | None = None
        self.echelle_scores: float = 0.05
        self.stats_marche: dict[str, dict[str, tuple[float, float]]] = {}
        self.metadonnees: dict[str, Any] = {}

    # -- Entrainement --------------------------------------------------------

    def entrainer(self, df: pd.DataFrame | None = None) -> "DetecteurAnomalies":
        df = df if df is not None else _generer_donnees_entrainement()

        df_modele = df.copy()
        df_modele["Profession"] = df_modele["Profession"].map(_bucket_profession)

        self.pipeline = _construire_pipeline()
        self.pipeline.fit(df_modele[CHAMPS_MODELE])
        self.scores_entrainement = np.sort(self.pipeline.decision_function(df_modele[CHAMPS_MODELE]))
        # Echelle de la fonction logistique (cf. _score_confiance) : calibree
        # pour que le score au 15e centile des profils d'ENTRAINEMENT (qui
        # sont par construction des profils plausibles) corresponde exactement
        # a SEUIL_NORMAL (85 %). Ainsi au moins ~85 % des profils typiques
        # obtiennent bien un score "Normal", et seule la queue statistique
        # (proche de la fraction contamination=0.06 utilisee par l'Isolation
        # Forest) tombe sous les seuils Atypique/Incoherent. L'ancienne echelle
        # (ecart interquartile) etait trop resserree : elle classait a tort
        # plus de la moitie des profils d'entrainement eux-memes en dessous du
        # seuil "Normal".
        s_p15 = np.percentile(self.scores_entrainement, 15)
        ratio_normal = SEUIL_NORMAL / (100 - SEUIL_NORMAL)  # 85/15
        self.echelle_scores = float(max(abs(s_p15) / np.log(ratio_normal), 1e-4))

        self.stats_marche = {
            marche: {
                champ: (float(groupe[champ].quantile(0.05)), float(groupe[champ].quantile(0.95)))
                for champ in CHAMPS_NUMERIQUES
            }
            for marche, groupe in df.groupby("Marche")
        }

        self.metadonnees = {
            "entraine_le": datetime.now().isoformat(timespec="seconds"),
            "n_echantillons": int(len(df)),
        }
        return self

    def sauvegarder(self) -> None:
        os.makedirs(DOSSIER_MODELE, exist_ok=True)
        dump(
            {
                "pipeline": self.pipeline,
                "scores_entrainement": self.scores_entrainement,
                "echelle_scores": self.echelle_scores,
                "stats_marche": self.stats_marche,
                "metadonnees": self.metadonnees,
            },
            CHEMIN_MODELE,
        )

    def charger(self) -> bool:
        if not os.path.exists(CHEMIN_MODELE):
            return False
        etat = load(CHEMIN_MODELE)
        self.pipeline = etat["pipeline"]
        self.scores_entrainement = etat["scores_entrainement"]
        self.echelle_scores = etat.get("echelle_scores", 0.05)
        self.stats_marche = etat["stats_marche"]
        self.metadonnees = etat.get("metadonnees", {})
        return True

    @classmethod
    def charger_ou_entrainer(cls) -> "DetecteurAnomalies":
        instance = cls()
        if not instance.charger():
            instance.entrainer()
            instance.sauvegarder()
        return instance

    # -- Analyse ---------------------------------------------------------------

    def _score_confiance(self, score_brut: float) -> int:
        """Convertit le score brut d'Isolation Forest en score de confiance (0-100 %).

        Isolation Forest situe sa frontiere normal/anormal a decision_function=0
        (cf. sklearn : `offset_` est calibre a partir de `contamination` pour que
        ce soit le cas). On applique une fonction logistique centree sur 0 et
        mise a l'echelle par la dispersion (IQR) des scores d'entrainement :
        cela evite qu'un simple rang percentile ne penalise a tort la masse des
        profils normaux (qui restent dispersés meme entre eux), tout en gardant
        0 = la frontiere exacte du modele (50 % de confiance).
        """
        if self.scores_entrainement is None or len(self.scores_entrainement) == 0:
            return 50
        z = score_brut / self.echelle_scores
        confiance = 100.0 / (1.0 + np.exp(-z))
        return int(round(max(0, min(100, confiance))))

    def _expliquer(self, profil: dict, marche: str) -> list[str]:
        explications: list[str] = []

        attendu = _COHERENCE_INDICATIVE.get(marche, {})
        for champ, val_attendue in attendu.items():
            val = str(profil.get(champ, "")).strip().capitalize()
            if val and val != val_attendue:
                explications.append(
                    f"{champ} = '{val}' inhabituel pour le marche {marche} "
                    f"(valeur generalement observee : '{val_attendue}')."
                )

        bornes_marche = self.stats_marche.get(marche, {})
        for champ in CHAMPS_NUMERIQUES:
            valeur = profil.get(champ)
            bornes = bornes_marche.get(champ)
            if valeur is None or not bornes:
                continue
            q05, q95 = bornes
            if valeur < q05:
                explications.append(
                    f"{champ} = {valeur:g} nettement inferieur aux profils habituels du marche "
                    f"{marche} (valeurs generalement observees a partir de {q05:.0f})."
                )
            elif valeur > q95:
                explications.append(
                    f"{champ} = {valeur:g} nettement superieur aux profils habituels du marche "
                    f"{marche} (valeurs generalement observees jusqu'a {q95:.0f})."
                )
        return explications

    @staticmethod
    def _ligne_modele(profil: dict) -> dict:
        """Convertit un profil client en une ligne de variables du modele.

        Extrait de analyser() pour etre partage avec analyser_dataframe : les
        deux chemins construisent ainsi EXACTEMENT les memes variables, et il
        n'existe qu'une seule definition de la mise en forme."""
        return {
            "Marche": str(profil.get("Marche", "")).upper().strip(),
            "Age": profil.get("Age") if profil.get("Age") is not None else 0,
            "MMM": profil.get("MMM") if profil.get("MMM") is not None else 0.0,
            "VRD": profil.get("VRD") if profil.get("VRD") is not None else 0.0,
            "Profession": _bucket_profession(profil.get("Profession")),
            "Nationalite": str(profil.get("Nationalite", "") or ""),
            "Residence": str(profil.get("Residence", "") or ""),
        }

    def _scores_bruts(self, profils: list[dict]) -> np.ndarray:
        """Score brut d'Isolation Forest pour N profils, en UN SEUL appel.

        Isolation Forest note chaque ligne independamment des autres : passer
        N lignes en un appel donne donc exactement les memes scores que N
        appels d'une ligne, pour un cout tres inferieur (l'essentiel du temps
        d'un appel scikit-learn est un cout fixe de validation et de
        transformation, paye une fois au lieu de N)."""
        if not profils:
            return np.empty(0)
        df = pd.DataFrame([self._ligne_modele(p) for p in profils])[CHAMPS_MODELE]
        return self.pipeline.decision_function(df)

    def _niveau(self, score_confiance: int) -> str:
        if score_confiance >= SEUIL_NORMAL:
            return "Normal"
        if score_confiance >= SEUIL_ATYPIQUE:
            return "Atypique"
        return "Incoherent"

    def analyser(self, profil: dict) -> dict:
        """Analyse un profil deja segmente par le moteur. Ne renvoie AUCUN
        segment / sous-segment : uniquement une analyse de coherence."""
        marche = str(profil.get("Marche", "")).upper().strip()
        score_brut = float(self._scores_bruts([profil])[0])
        score_confiance = self._score_confiance(score_brut)
        niveau = self._niveau(score_confiance)

        explications = self._expliquer(profil, marche)
        if niveau == "Normal" and not explications:
            explications = [
                "Aucune anomalie detectee : profil statistiquement coherent avec les profils "
                "habituels de ce marche."
            ]
        elif not explications:
            explications = [
                "Combinaison de criteres peu frequente pour ce marche, detectee par le modele "
                "statistique (Isolation Forest). Une verification est recommandee."
            ]

        return {
            "anomalie": niveau != "Normal",
            "score_anomalie": round(score_brut, 4),
            "score_confiance": score_confiance,
            "niveau": niveau,
            "emoji": EMOJI_NIVEAU[niveau],
            "explications": explications,
        }

    def analyser_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Analyse chaque ligne d'un DataFrame deja segmente ; renvoie les
        colonnes ML_Anomalie / ML_Confiance / ML_Niveau alignees sur l'index
        du DataFrame d'entree (a concatener par l'appelant).

        Analyse VECTORISEE : un seul appel au modele pour tout le lot.

        La version precedente appelait analyser() ligne par ligne
        (df.iterrows()), donc reconstruisait un DataFrame d'une ligne et
        invoquait scikit-learn N fois -- 5 000 lignes prenaient 73 s, cout
        repaye a chaque interaction Streamlit tant que le fichier restait
        charge. Elle calculait de surcroit, pour chaque ligne, des explications
        textuelles aussitot jetees (ce tableau ne renvoie que anomalie,
        confiance et niveau).

        Les valeurs produites sont strictement identiques : Isolation Forest
        note chaque ligne independamment (verifie par tests/test_ml.py sur
        2 000 profils, scores bruts compares au bit pres)."""
        if df.empty:
            return pd.DataFrame(
                {"ML_Anomalie": [], "ML_Confiance": [], "ML_Niveau": []}, index=df.index
            )
        scores = self._scores_bruts(df.to_dict("records"))
        confiances = [self._score_confiance(float(s)) for s in scores]
        niveaux = [self._niveau(c) for c in confiances]
        return pd.DataFrame(
            {
                "ML_Anomalie": [n != "Normal" for n in niveaux],
                "ML_Confiance": confiances,
                "ML_Niveau": niveaux,
            },
            index=df.index,
        )


# --------------------------------------------------------------------------- #
# Instance partagee (chargee ou entrainee une seule fois par processus)
# --------------------------------------------------------------------------- #

_DETECTEUR: DetecteurAnomalies | None = None


def _detecteur() -> DetecteurAnomalies:
    global _DETECTEUR
    if _DETECTEUR is None:
        _DETECTEUR = DetecteurAnomalies.charger_ou_entrainer()
    return _DETECTEUR


def analyser_anomalie(profil: dict) -> dict:
    """Point d'entree principal : analyse un profil DEJA segmente par le
    moteur officiel. Ne modifie et ne recalcule JAMAIS le segment."""
    return _detecteur().analyser(profil)


def analyser_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Analyse en masse (import CSV) : voir DetecteurAnomalies.analyser_dataframe."""
    return _detecteur().analyser_dataframe(df)


def infos_modele() -> dict:
    """Metadonnees du modele actuellement charge (date d'entrainement, taille)."""
    return dict(_detecteur().metadonnees)


def reentrainer_modele() -> dict:
    """Force un reentrainement complet du modele (ex. depuis la page Tableau de bord)."""
    global _DETECTEUR
    _DETECTEUR = DetecteurAnomalies().entrainer()
    _DETECTEUR.sauvegarder()
    return _DETECTEUR.metadonnees
