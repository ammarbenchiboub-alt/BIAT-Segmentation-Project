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

from commun import en_mD
from core import MoteurSegmentation

MESSAGE_ABSENT = "La reponse n'est pas disponible dans le document metier."


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", str(t).lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _contient_mot(cle: str, question: str) -> bool:
    """Vrai si `cle` apparait comme MOT ENTIER dans `question`.

    Remplace le test `cle in question` (recherche de sous-chaine), qui
    produisait des faux positifs massifs : un mot-cle etait reconnu des qu'il
    apparaissait a l'INTERIEUR d'un autre mot. Exemples reellement observes :

        cle 'and'    trouvee dans "qu-and je modifie le MMM"
        cle 'change' trouvee dans "ca change quoi" (verbe usuel), alors qu'elle
                     designe la "reglementation de change"
        cle 'ou'     trouvee dans "p-ou-vez", "p-ou-r"
        cle 'pl'     trouvee dans "ex-pl-iquer", "exem-pl-e"
        cle 'tre'    trouvee dans "au-tre", "no-tre", "e-tre"

    La quasi-totalite des questions formulees en langage naturel declenchait
    ainsi au moins une correspondance parasite, et le chatbot repondait a cote.

    Les bornes de mot (\\b) suppriment ces correspondances internes. Les formes
    plurielles ne sont volontairement PAS tolerees automatiquement (un
    `\\bcle s?\\b` ferait correspondre la cle 'tre' au mot tres frequent
    "tres") : la base de connaissances declare explicitement les variantes
    utiles ('marche'/'marches', 'liberale'/'liberales', ...).
    """
    return re.search(rf"\b{re.escape(cle)}\b", question) is not None


class ChatbotExpert:
    def __init__(self, moteur: MoteurSegmentation | None = None):
        self.moteur = moteur or MoteurSegmentation()
        self._index_regles = {
            regle["id"]: regle
            for marche in self.moteur.marches.values()
            for regle in marche["regles"]
        }
        self.kb = self._construire_kb()

    # -------------------------------------------------- lecture des seuils
    def _seuil(self, regle_id: str, champ: str, borne: str) -> str:
        """Renvoie un seuil formate en mD, LU DEPUIS LA SOURCE UNIQUE.

        Les seuils cites par le chatbot etaient auparavant ecrits en dur dans
        le texte des reponses. Ils constituaient donc une SECONDE COPIE des
        regles, en contradiction directe avec le principe fondateur du projet
        (config/regles_segmentation.json = source unique).

        Ce defaut s'etait deja materialise : la correction des seuils MMM du
        marche TRE (voir _notes_conflits.tre_mmm_vs_revenu_CORRIGE dans le
        JSON -- colonne Revenus confondue avec colonne MMM) avait ete appliquee
        au fichier de regles mais PAS au texte du chatbot. Celui-ci annoncait
        donc aux conseillers des seuils TRE que le moteur n'appliquait plus
        (10 mD et 5 mD au lieu de 2,5 mD et 1 mD).

        En derivant les valeurs des regles, le chatbot ne peut plus diverger :
        toute modification validee en page Parametrage est immediatement
        reflechie dans ses reponses. Les listes de professions etaient deja
        construites ainsi (liste_professions) ; ce principe est simplement
        etendu aux valeurs numeriques.

        L'unite d'affichage reste le mD (millier de dinars), unite de la note ;
        le JSON stocke des DT. La conversion est purement presentationnelle.
        """
        regle = self._index_regles.get(regle_id)
        if not regle:  # pragma: no cover - garde-fou
            return "?"
        bornes = regle["conditions"].get(champ) or {}
        valeur = bornes.get(borne)
        if valeur is None:  # pragma: no cover - garde-fou
            return "?"
        # Conversion DT -> mD centralisee dans commun.formatage : une seule
        # definition partagee avec le referentiel et la fiche de decision.
        return en_mD(valeur)

    def _plage(self, regle_id: str, champ: str) -> str:
        """Formate un intervalle sous la forme '25-50 mD' (et non
        '25 mD-50 mD') : l'unite n'est repetee qu'une fois, comme dans la
        redaction d'origine de la note."""
        mini = self._seuil(regle_id, champ, "min")
        maxi = self._seuil(regle_id, champ, "max")
        return f"{mini.removesuffix(' mD')}-{maxi}"

    def _age_min(self, regle_id: str) -> str:
        """Age plancher exprime comme dans la note : la regle porte
        'age >= 31', la note dit 'plus de 30 ans'. On renvoie donc la borne
        moins un, pour rester fidele a la formulation d'origine tout en
        derivant la valeur de la source unique."""
        regle = self._index_regles.get(regle_id)
        borne = (regle["conditions"].get("age") or {}).get("min") if regle else None
        return str(borne - 1) if borne else "?"

    # ------------------------------------------------------------------ KB
    def _construire_kb(self) -> list[dict]:
        """Base de connaissances : chaque entree = mots-cles + reponse sourcee.

        Les TEXTES de reponse sont issus exclusivement de la Note BIAT 2023-06 :
        ils ne doivent jamais etre modifies pour des raisons techniques. Seuls
        les MOTS-CLES (metadonnees de recherche, sans valeur metier) ont ete
        revus pour supprimer ceux qui produisaient des correspondances
        parasites -- voir _contient_mot :

          - 'ou', 'and', 'or' (entree MMM/VRD) : retires. Ce sont des
            operateurs logiques, inexploitables comme mots-cles ('ou' est la
            preposition la plus courante du francais). L'entree reste atteinte
            par 'mmm', 'vrd', 'combinaison' et 'logique' -- une question du
            type "MMM ou VRD ?" continue donc d'y repondre.
          - 'change' (entree Residence) : remplace par la locution complete
            "reglementation de change". Isole, 'change' est un verbe usuel qui
            faisait repondre sur la residence a des questions sans rapport.
        """
        m = self.moteur
        pl = ", ".join(m.liste_professions("professions_liberales_annexe5_toutes"))
        pot_hg = ", ".join(m.liste_professions("professions_a_potentiel_HG_annexe4"))
        pot_sal = ", ".join(m.liste_professions("professions_a_potentiel_salaries_annexe4"))
        return [
            {"cles": ["marche", "marches", "geres", "part pro tre enr", "tpme"],
             "rep": "Les marches geres sont PART (Particuliers), PRO (Professionnels), TRE (Tunisiens Residents a l'Etranger) et ENR (Etrangers Non Residents). Le marche TPME n'est pas gere par cette application."},
            {"cles": ["mmm", "vrd", "combinaison", "logique"],
             "rep": "La condition entre MMM et VRD est un OU logique (OR), jamais un ET. Un client atteint un palier des que le MMM OU le VRD satisfait le seuil. La note ENR l'ecrit explicitement : 'MMM ou Total des avoirs'."},
            {"cles": ["fortune", "fortunes"],
             "rep": f"Fortunes (Haut de Gamme, PART & PRO) : quel que soit l'age, "
                    f"VRD >= {self._seuil('PART_HDG_FORTUNES', 'vrd', 'min')}."},
            {"cles": ["patrimoniaux"],
             "rep": f"Patrimoniaux (PART, Haut de Gamme) : plus de {self._age_min('PART_HDG_PATRIMONIAUX')} ans, "
                    f"MMM >= {self._seuil('PART_HDG_PATRIMONIAUX', 'mmm', 'min')} OU VRD entre "
                    f"{self._plage('PART_HDG_PATRIMONIAUX', 'vrd').replace('-', ' et ')}."},
            {"cles": ["affluent", "affluents"],
             "rep": f"Affluent (PART, Haut de Gamme) : plus de {self._age_min('PART_HDG_AFFLUENT')} ans, "
                    f"MMM >= {self._seuil('PART_HDG_AFFLUENT', 'mmm', 'min')} OU VRD entre "
                    f"{self._plage('PART_HDG_AFFLUENT', 'vrd').replace('-', ' et ')}. Les professions a potentiel "
                    f"(annexe 4) sont integrees a l'Affluent independamment du MMM."},
            {"cles": ["professionnels"],
             "rep": f"Professionnels (PRO, Haut de Gamme) : "
                    f"MMM >= {self._seuil('PRO_HDG_PROFESSIONNELS', 'mmm', 'min')} OU "
                    f"VRD >= {self._seuil('PRO_HDG_PROFESSIONNELS', 'vrd', 'min')} "
                    f"(professions a potentiel hors PL)."},
            {"cles": ["profession liberale", "liberale", "liberales", "pl"],
             "rep": f"Professions Liberales (PRO, Haut de Gamme) : profession liberale declaree, quel que soit l'age et le montant. Liste (annexe 5) : {pl}."},
            {"cles": ["classe moyenne", "salaries", "commercants", "artisans"],
             "rep": f"Classe Moyenne : PART 'Les salaries' (secteur public) "
                    f"MMM {self._plage('PART_CM_SALARIES', 'mmm')} OU "
                    f"VRD {self._plage('PART_CM_SALARIES', 'vrd')} ; "
                    f"PRO 'Commercants & Artisans' "
                    f"MMM {self._plage('PRO_CM_COMMERCANTS', 'mmm')} OU "
                    f"VRD {self._plage('PRO_CM_COMMERCANTS', 'vrd')}."},
            {"cles": ["grand public", "dormant", "dormants"],
             "rep": f"Grand Public : PART Particuliers "
                    f"MMM < {self._seuil('PART_GP_PARTICULIERS', 'mmm', 'max')} OU "
                    f"VRD < {self._seuil('PART_GP_PARTICULIERS', 'vrd', 'max')} ; "
                    f"PRO Commercants & Artisans "
                    f"MMM < {self._seuil('PRO_GP_COMMERCANTS', 'mmm', 'max')} OU "
                    f"VRD < {self._seuil('PRO_GP_COMMERCANTS', 'vrd', 'max')}. "
                    f"Clients dormants : montants tres faibles et 0 operation sur 12 mois."},
            {"cles": ["jeunes", "jda", "enfants", "eleves", "etudiant", "etudiants"],
             "rep": f"Les Jeunes (PART) : Enfants et Eleves (<= 18 ans) ; Etudiants (profession "
                    f"Etudiant, tout age) ; JDA a potentiel (>18 et <=30 ans, profession a "
                    f"potentiel) ; Autres JDA (>18 et <=30 ans). Seuils : "
                    f"MMM < {self._seuil('PART_JEUNES_AUTRES_JDA', 'mmm', 'max')}, "
                    f"VRD < {self._seuil('PART_JEUNES_AUTRES_JDA', 'vrd', 'max')}."},
            {"cles": ["tre", "resident etranger", "residents a l'etranger"],
             "rep": f"TRE : Premium (profession a potentiel OU "
                    f"MMM >= {self._seuil('TRE_PREMIUM_MONTANT', 'mmm', 'min')} OU "
                    f"VRD >= {self._seuil('TRE_PREMIUM_MONTANT', 'vrd', 'min')}) ; "
                    f"Potentiel moyen (MMM >= {self._seuil('TRE_POTENTIEL_MOYEN', 'mmm', 'min')} OU "
                    f"VRD {self._plage('TRE_POTENTIEL_MOYEN', 'vrd')}) ; "
                    f"Faible potentiel (MMM < {self._seuil('TRE_FAIBLE_POTENTIEL', 'mmm', 'max')}, "
                    f"VRD < {self._seuil('TRE_FAIBLE_POTENTIEL', 'vrd', 'max')}) ; "
                    f"TRE Inactif (comptes non mouvementes 1 an)."},
            {"cles": ["enr", "etranger non resident", "non resident"],
             "rep": f"ENR : Premium (MMM >= {self._seuil('ENR_PREMIUM', 'mmm', 'min')} OU "
                    f"VRD >= {self._seuil('ENR_PREMIUM', 'vrd', 'min')}) ; "
                    f"Potentiel moyen (MMM >= {self._seuil('ENR_POTENTIEL_MOYEN', 'mmm', 'min')} OU "
                    f"VRD {self._plage('ENR_POTENTIEL_MOYEN', 'vrd')}) ; "
                    f"Faible potentiel (MMM < {self._seuil('ENR_FAIBLE_POTENTIEL', 'mmm', 'max')}, "
                    f"VRD < {self._seuil('ENR_FAIBLE_POTENTIEL', 'vrd', 'max')}) ; "
                    f"Inactifs (comptes non mouvementes 1 an)."},
            {"cles": ["residence", "titre de sejour", "reglementation de change"],
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
            score = sum(1 for cle in entree["cles"] if _contient_mot(_norm(cle), q))
            if score:
                meilleures.append((score, entree["rep"]))
        if meilleures:
            meilleures.sort(key=lambda x: -x[0])
            # Seules les entrees AUSSI pertinentes que la meilleure sont
            # retenues. Le code precedent renvoyait systematiquement les deux
            # premieres, quel que soit leur ecart de score : une entree ayant
            # obtenu 1 point par un mot-cle marginal etait presentee au meme
            # rang qu'une entree en ayant obtenu 3. L'utilisateur recevait donc
            # une reponse juste suivie d'une reponse hors sujet, sans pouvoir
            # distinguer laquelle repondait a sa question.
            score_max = meilleures[0][0]
            reps, vus = [], set()
            for score, rep in meilleures:
                if score < score_max:
                    break
                if rep not in vus:
                    reps.append(rep)
                    vus.add(rep)
            # Plafond de securite : au-dela de deux reponses a egalite, la
            # question est trop vague pour qu'un empilement soit utile.
            return {"type": "connaissance", "source": "Note BIAT 2023-06",
                    "reponse": "\n\n".join(reps[:2])}

        # 3) Absence d'information
        return {"type": "absent", "source": "Note BIAT 2023-06", "reponse": MESSAGE_ABSENT}
