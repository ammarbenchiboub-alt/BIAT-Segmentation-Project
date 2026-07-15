"""
ASSISTANT IA D'AIDE A LA DECISION (cohérence)

L'assistant travaille APRES chaque segmentation. Il :
  - verifie la coherence du profil et du resultat,
  - detecte les incoherences / contradictions,
  - verifie la proximite des seuils (cas limites),
  - calcule un score de confiance,
  - produit alertes, recommandations et explications.

Il NE MODIFIE JAMAIS le segment calcule par le moteur unique.
Il ne remplace pas le moteur : il l'eclaire.
"""
from __future__ import annotations

from core import MoteurSegmentation, ResultatSegmentation

# Coherence attendue marche <-> residence / nationalite (indicative)
_ATTENDU = {
    "PART": {"Residence": "Oui"},
    "PRO": {"Residence": "Oui"},
    "TRE": {"Residence": "Non", "Nationalite": "Tunisienne"},
    "ENR": {"Residence": "Non", "Nationalite": "Autre"},
}

# Marge de proximite d'un seuil (10 %) pour signaler un cas limite
_MARGE = 0.10


class AssistantIA:
    def __init__(self, moteur: MoteurSegmentation | None = None):
        self.moteur = moteur or MoteurSegmentation()

    def _regle(self, marche: str, regle_id: str | None) -> dict | None:
        if not regle_id:
            return None
        for r in self.moteur.marches.get(marche, {}).get("regles", []):
            if r["id"] == regle_id:
                return r
        return None

    def analyser(self, resultat: ResultatSegmentation) -> dict:
        profil = resultat.profil
        alertes: list[str] = []
        recommandations: list[str] = []
        coherences: list[str] = []
        score = 100

        # 1) Resultat obtenu ?
        if not resultat.succes:
            alertes.append("Aucun segment determine : profil hors des regles de la note. Clarification requise.")
            score -= 50

        # 2) Champs essentiels presents
        for champ in ("Age", "MMM", "VRD"):
            if profil.get(champ) in (None, ""):
                alertes.append(f"Champ '{champ}' manquant : la fiabilite du resultat est reduite.")
                score -= 12

        # 3) Coherence marche <-> residence / nationalite
        attendu = _ATTENDU.get(resultat.marche, {})
        for champ, val_attendue in attendu.items():
            val = str(profil.get(champ, "")).strip().capitalize()
            if val and val != val_attendue:
                alertes.append(
                    f"Incoherence possible : pour le marche {resultat.marche}, "
                    f"'{champ}' attendu = {val_attendue}, saisi = {val}."
                )
                score -= 8
            elif val == val_attendue:
                coherences.append(f"{champ} = {val_attendue} coherent avec le marche {resultat.marche}.")

        # 4) Proximite des seuils (cas limite)
        regle = self._regle(resultat.marche, resultat.regle_id)
        if regle:
            for var in ("mmm", "vrd"):
                borne = regle["conditions"].get(var, {})
                valeur = profil.get(var.upper())
                if valeur is None:
                    continue
                for cle in ("min", "max"):
                    seuil = borne.get(cle)
                    if seuil and seuil > 0 and abs(valeur - seuil) <= _MARGE * seuil:
                        alertes.append(
                            f"Cas limite : {var.upper()}={valeur} proche du seuil {seuil} DT "
                            f"({'entree' if cle == 'min' else 'sortie'} de palier). A verifier."
                        )
                        recommandations.append(
                            f"Verifier {var.upper()} : une faible variation change le sous-segment."
                        )
                        score -= 6

        # 5) Recommandations metier neutres
        if resultat.succes:
            coherences.append(
                f"Segment '{resultat.segment} / {resultat.sous_segment}' issu de la regle {resultat.regle_id}."
            )
            if resultat.segment in ("Haut de Gamme", "Premium"):
                recommandations.append("Client a fort potentiel : orienter vers une prise en charge dediee (conseiller HDG / Premium).")
            if resultat.sous_segment in ("Autres JDA", "Enfants et Eleves", "Etudiants"):
                recommandations.append("Segment jeune : proposer une offre d'equipement et de fidelisation adaptee.")

        score = max(0, min(100, score))
        if not alertes:
            coherences.append("Aucune incoherence detectee sur les champs disponibles.")

        return {
            "score_confiance": score,
            "niveau": self._niveau(score),
            "alertes": alertes,
            "recommandations": sorted(set(recommandations)),
            "coherences": coherences,
            "explications": resultat.explications,
        }

    @staticmethod
    def _niveau(score: int) -> str:
        if score >= 85:
            return "Eleve"
        if score >= 60:
            return "Moyen"
        return "Faible"
