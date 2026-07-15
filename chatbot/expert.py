"""
CHATBOT EXPERT METIER BANCAIRE - BIAT

Ce chatbot n'est PAS generaliste. Il repond uniquement a partir :
  1) de la Note BIAT 2023-06 (base de connaissances structuree ci-dessous) ;
  2) du moteur unique de segmentation (pour l'aide a la decision).

Il n'invente jamais de regle. Si l'information est absente, il repond :
  "La reponse n'est pas disponible dans le document metier."

Aide a la decision : lorsqu'un profil client est fourni (en texte libre ou
via un dictionnaire), le chatbot appelle EXCLUSIVEMENT le moteur unique.
"""
from __future__ import annotations

import re
import unicodedata

from core import MoteurSegmentation

MESSAGE_ABSENT = "La reponse n'est pas disponible dans le document metier."


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


class ChatbotExpert:
    def __init__(self, moteur: MoteurSegmentation | None = None):
        self.moteur = moteur or MoteurSegmentation()
        self.kb = self._construire_kb()

    # ------------------------------------------------------------------ KB
    def _construire_kb(self) -> list[dict]:
        """Base de connaissances : chaque entree = mots-cles + reponse sourcee."""
        m = self.moteur
        pl = ", ".join(m.liste_professions("professions_liberales_annexe5_toutes"))
        pot_hg = ", ".join(m.liste_professions("professions_a_potentiel_HG_annexe4"))
        pot_sal = ", ".join(m.liste_professions("professions_a_potentiel_salaries_annexe4"))
        return [
            {"cles": ["marche", "marches", "geres", "part pro tre enr", "tpme"],
             "rep": "Les marches geres sont PART (Particuliers), PRO (Professionnels), TRE (Tunisiens Residents a l'Etranger) et ENR (Etrangers Non Residents). Le marche TPME n'est pas gere par cette application."},
            {"cles": ["mmm", "vrd", "ou", "and", "or", "combinaison", "logique"],
             "rep": "La condition entre MMM et VRD est un OU logique (OR), jamais un ET. Un client atteint un palier des que le MMM OU le VRD satisfait le seuil. La note ENR l'ecrit explicitement : 'MMM ou Total des avoirs'."},
            {"cles": ["fortune", "fortunes", "500"],
             "rep": "Fortunes (Haut de Gamme, PART & PRO) : quel que soit l'age, VRD >= 500 mD."},
            {"cles": ["patrimoniaux", "300", "500"],
             "rep": "Patrimoniaux (PART, Haut de Gamme) : plus de 30 ans, MMM >= 10 mD OU VRD entre 300 et 500 mD."},
            {"cles": ["affluent", "affluents", "100", "300"],
             "rep": "Affluent (PART, Haut de Gamme) : plus de 30 ans, MMM >= 4 mD OU VRD entre 100 et 300 mD. Les professions a potentiel (annexe 4) sont integrees a l'Affluent independamment du MMM."},
            {"cles": ["professionnels", "100 md", "200 md"],
             "rep": "Professionnels (PRO, Haut de Gamme) : MMM >= 100 mD OU VRD >= 200 mD (professions a potentiel hors PL)."},
            {"cles": ["profession liberale", "liberale", "liberales", "pl"],
             "rep": f"Professions Liberales (PRO, Haut de Gamme) : profession liberale declaree, quel que soit l'age et le montant. Liste (annexe 5) : {pl}."},
            {"cles": ["classe moyenne", "salaries", "commercants", "artisans"],
             "rep": "Classe Moyenne : PART 'Les salaries' (secteur public) MMM 1-4 mD OU VRD 5-100 mD ; PRO 'Commercants & Artisans' MMM 5-100 mD OU VRD 15-200 mD."},
            {"cles": ["grand public", "dormant", "dormants"],
             "rep": "Grand Public : PART Particuliers MMM < 1 mD OU VRD < 5 mD ; PRO Commercants & Artisans MMM < 5 mD OU VRD < 15 mD. Clients dormants : montants tres faibles et 0 operation sur 12 mois."},
            {"cles": ["jeunes", "jda", "enfants", "eleves", "etudiant", "etudiants"],
             "rep": "Les Jeunes (PART) : Enfants et Eleves (<= 18 ans) ; Etudiants (profession Etudiant, tout age) ; JDA a potentiel (>18 et <=30 ans, profession a potentiel) ; Autres JDA (>18 et <=30 ans). Seuils : MMM < 10 mD, VRD < 300 mD."},
            {"cles": ["tre", "resident etranger", "residents a l'etranger"],
             "rep": "TRE : Premium (profession a potentiel OU MMM >= 10 mD OU VRD >= 50 mD) ; Potentiel moyen (MMM >= 5 mD OU VRD 25-50 mD) ; Faible potentiel (MMM < 5 mD, VRD < 25 mD) ; TRE Inactif (comptes non mouvementes 1 an)."},
            {"cles": ["enr", "etranger non resident", "non resident"],
             "rep": "ENR : Premium (MMM >= 10 mD OU VRD >= 60 mD) ; Potentiel moyen (MMM >= 5 mD OU VRD 30-60 mD) ; Faible potentiel (MMM < 5 mD, VRD < 30 mD) ; Inactifs (comptes non mouvementes 1 an)."},
            {"cles": ["residence", "titre de sejour", "change"],
             "rep": "Residence : le TRE respecte la reglementation de change (centre d'interet a l'etranger, titre de sejour valide ; statut maintenu 2 ans max apres retour definitif). L'ENR ne detient pas de titre de sejour en Tunisie (sejour <= 3 mois successifs)."},
            {"cles": ["annexe 4", "profession a potentiel", "potentiel"],
             "rep": f"Professions a potentiel (annexe 4). Professionnels HG : {pot_hg}. Salaries (Affluents / TRE Premium / JDA Potentiel) : {pot_sal}."},
            {"cles": ["annexe 5", "professions liberales", "strategiques"],
             "rep": f"Professions liberales (annexe 5) : {pl}."},
            {"cles": ["segment", "segments", "sous-segment", "liste des segments"],
             "rep": "Segments principaux : Haut de Gamme, Classe Moyenne, Grand Public, Les Jeunes (PART/PRO) ; Premium, Potentiel moyen, Faible potentiel, Inactif (TRE/ENR)."},
            {"cles": ["revenus", "nombre d'operations", "operations"],
             "rep": "Dans la simulation individuelle, les Revenus et le Nombre d'operations ne sont pas utilises. Les champs actifs sont : Marche, Profession, Age, MMM, VRD, Nationalite, Residence."},
        ]

    # ------------------------------------------------ extraction de profil
    _CHAMPS = {
        "Marche": r"march[ée]\s*[:=]?\s*([A-Za-z]{3,4})",
        "Profession": r"profession\s*[:=]?\s*([A-Za-zÀ-ÿ' \-]+?)(?:\s+age|\s+[a-zç]+\s*[:=]|$)",
        "Age": r"[âa]ge\s*[:=]?\s*(\d{1,3})",
        "MMM": r"\bmmm\s*[:=]?\s*([\d\s.,]+)",
        "VRD": r"\bvrd\s*[:=]?\s*([\d\s.,]+)",
        "Nationalite": r"nationalit[ée]\s*[:=]?\s*([A-Za-zÀ-ÿ]+)",
        "Residence": r"r[ée]sidence\s*[:=]?\s*(oui|non)",
    }

    def _extraire_profil(self, texte: str) -> dict | None:
        profil = {}
        for champ, motif in self._CHAMPS.items():
            m = re.search(motif, texte, flags=re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if champ in ("Age",):
                    profil[champ] = int(val)
                elif champ in ("MMM", "VRD"):
                    num = re.sub(r"[^\d.,]", "", val).replace(",", ".")
                    if num:
                        profil[champ] = float(num)
                elif champ == "Marche":
                    profil[champ] = val.upper()
                else:
                    profil[champ] = val
        # Il faut au minimum le marche et un montant pour segmenter.
        if "Marche" in profil and ("MMM" in profil or "VRD" in profil):
            profil.setdefault("MMM", 0)
            profil.setdefault("VRD", 0)
            return profil
        return None

    # --------------------------------------------------- aide a la decision
    def analyser_profil(self, profil: dict) -> dict:
        """Analyse un profil via le moteur UNIQUE et explique chaque etape."""
        r = self.moteur.segmenter(profil)
        lignes = ["Analyse du profil (via le moteur unique) :", ""]
        for k in ("Marche", "Profession", "Age", "MMM", "VRD", "Nationalite", "Residence"):
            if k in profil and profil[k] not in ("", None):
                lignes.append(f"  - {k} : {profil[k]}")
        lignes.append("")
        if r.succes:
            lignes.append(f"=> Segment : {r.segment}")
            lignes.append(f"=> Sous-segment : {r.sous_segment}")
            lignes.append(f"=> Regle appliquee : {r.regle_id}")
            lignes.append("")
            lignes.append("Etapes d'evaluation :")
            lignes += [f"  {e}" for e in r.explications]
        else:
            lignes.append(r.message)
        return {"type": "aide_decision", "source": "Moteur unique + Note BIAT 2023-06",
                "reponse": "\n".join(lignes), "resultat": r}

    # ------------------------------------------------------------ reponse
    def repondre(self, question: str) -> dict:
        if not question or not question.strip():
            return {"type": "vide", "source": None, "reponse": "Posez une question sur la segmentation BIAT."}

        # 1) Aide a la decision si un profil est detecte
        profil = self._extraire_profil(question)
        if profil is not None:
            return self.analyser_profil(profil)

        # 2) Recherche dans la base de connaissances
        q = _norm(question)
        meilleures = []
        for entree in self.kb:
            score = sum(1 for cle in entree["cles"] if _norm(cle) in q)
            if score:
                meilleures.append((score, entree["rep"]))
        if meilleures:
            meilleures.sort(key=lambda x: -x[0])
            reps = []
            vus = set()
            for _, rep in meilleures[:2]:
                if rep not in vus:
                    reps.append(rep)
                    vus.add(rep)
            return {"type": "connaissance", "source": "Note BIAT 2023-06", "reponse": "\n\n".join(reps)}

        # 3) Absence d'information
        return {"type": "absent", "source": "Note BIAT 2023-06", "reponse": MESSAGE_ABSENT}
