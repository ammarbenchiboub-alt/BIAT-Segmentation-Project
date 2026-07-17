"""Tests du chatbot expert metier.

Non-regression d'un defaut signale par l'utilisateur en usage reel : a la
question « quand je modifier le mmm ca change quoi ? », le chatbot repondait
correctement sur la logique MMM/VRD, puis enchainait sur un paragraphe
consacre a la RESIDENCE et a la reglementation de change, totalement etranger
a la question.

Trois causes cumulees, toutes corrigees :

  1. Recherche par SOUS-CHAINE (`cle in question`) : un mot-cle etait reconnu
     des qu'il apparaissait a l'interieur d'un autre mot.
        'and'    reconnue dans "qu-and"
        'change' reconnue dans "ca change quoi" (verbe usuel) alors qu'elle
                 designe la "reglementation de change"
        'ou'     reconnue dans "p-ou-vez", "p-ou-r"
        'tre'    reconnue dans "au-tre", "no-tre"
  2. Mots-cles inexploitables ('ou', 'and', 'or' : des operateurs logiques).
  3. Les DEUX meilleures entrees etaient renvoyees quel que soit leur ecart de
     score : une entree a 1 point parasite etait presentee au meme rang qu'une
     entree a 2 points pertinents.

Ces tests portent sur la RECHERCHE, jamais sur le contenu des reponses : les
textes proviennent de la Note BIAT 2023-06 et ne sont pas modifiables pour des
raisons techniques.
"""
from __future__ import annotations


import sys

from _outils import Resultats

import chatbot.expert as module_chatbot
from chatbot.expert import MESSAGE_ABSENT, ChatbotExpert, _contient_mot, _norm
from core import MoteurSegmentation, charger_regles


def run() -> bool:
    r = Resultats("chatbot expert metier")
    chatbot = ChatbotExpert(MoteurSegmentation())

    # ================================================================== #
    # 1. Le defaut signale par l'utilisateur
    # ================================================================== #
    reponse = chatbot.repondre("quand je modifier le mmm ca change quoi ?")["reponse"]
    r.verifier("la question sur le MMM repond bien sur la logique MMM/VRD",
               "OU logique" in reponse)
    r.verifier("  et NE PART PLUS sur la residence / reglementation de change",
               "titre de sejour" not in reponse and "reglementation de change" not in reponse,
               f"obtenu : {reponse[:120]}")

    # ================================================================== #
    # 2. Correspondances internes aux mots : la cause racine
    # ================================================================== #
    fragments = [
        ("and", "quand je modifie le mmm"),
        ("ou", "pouvez vous expliquer les segments"),
        ("ou", "quel est le seuil pour un commercant"),
        ("or", "alors quels sont les seuils"),
        ("pl", "par exemple un client jeune"),
        ("pl", "pouvez vous expliquer les seuils"),
        ("tre", "quelle est la logique entre mmm et vrd"),
        ("tre", "montre moi une autre regle"),
        ("enr", "comment enregistrer un client"),
    ]
    for cle, phrase in fragments:
        r.verifier(f"'{cle}' n'est plus reconnue dans \"{phrase[:38]}...\"",
                   not _contient_mot(cle, _norm(phrase)))

    # Les mots entiers, eux, restent bien reconnus.
    for cle, phrase in [("mmm", "quel est le mmm ?"), ("tre", "les seuils TRE ?"),
                        ("enr", "segment ENR ?"), ("pl", "c'est une PL ?"),
                        ("500", "le seuil de 500 mD ?")]:
        r.verifier(f"'{cle}' reste reconnue comme mot entier dans \"{phrase}\"",
                   _contient_mot(cle, _norm(phrase)))

    # ================================================================== #
    # 3. Mots-cles parasites retires de la base de connaissances
    # ================================================================== #
    toutes_cles = [c for e in chatbot.kb for c in e["cles"]]
    for parasite in ("ou", "and", "or"):
        r.verifier(f"le mot-cle inexploitable '{parasite}' a ete retire",
                   parasite not in toutes_cles)
    r.verifier("'change' seul remplace par la locution complete",
               "change" not in toutes_cles and "reglementation de change" in toutes_cles)

    # Retirer 'ou' ne doit pas empecher de repondre a "MMM ou VRD ?".
    r.verifier("\"MMM ou VRD ?\" trouve toujours sa reponse",
               "OU logique" in chatbot.repondre("MMM ou VRD ?")["reponse"])

    # ================================================================== #
    # 4. Seules les entrees aussi pertinentes que la meilleure sont rendues
    # ================================================================== #
    reponse_ciblee = chatbot.repondre("Quels sont les seuils du segment Affluent ?")["reponse"]
    r.verifier("une question ciblee donne UNE reponse, pas un empilement",
               reponse_ciblee.count("\n\n") <= 1)
    r.verifier("  et c'est la bonne", "Affluent" in reponse_ciblee)

    # ================================================================== #
    # 5. Non-regression : les exemples proposes dans l'interface
    # ================================================================== #
    attendus = [
        ("Quelle est la logique entre MMM et VRD ?", "OU logique"),
        ("Quels sont les seuils du segment Affluent ?", "Affluent"),
        ("Liste des professions liberales ?", "Professions Liberales"),
        ("Quels sont les marches geres ?", "PART"),
        ("Quels sont les seuils TRE ?", "TRE"),
        ("Segment ENR ?", "ENR"),
        ("Qu'est-ce qu'un client dormant ?", "dormant"),
        ("Les revenus sont-ils utilises ?", "Revenus"),
    ]
    for question, attendu in attendus:
        r.verifier(f"\"{question[:42]}...\" -> reponse pertinente",
                   attendu.lower() in chatbot.repondre(question)["reponse"].lower())

    # ================================================================== #
    # 6. Aide a la decision : delegation au MOTEUR UNIQUE
    # ================================================================== #
    sortie = chatbot.repondre("Marche = PRO Profession = Commercant Age = 40 MMM = 90 VRD = 3")
    r.egal("un profil declenche l'aide a la decision", sortie["type"], "aide_decision")
    r.verifier("  le resultat provient du moteur", "resultat" in sortie)

    # Le chatbot ne doit JAMAIS recalculer un segment lui-meme : sa reponse
    # doit coincider avec celle du moteur appele directement.
    profil = {"Marche": "PRO", "Profession": "Commercant", "Age": 40, "MMM": 90.0, "VRD": 3.0}
    attendu_moteur = MoteurSegmentation().segmenter(profil)
    r.egal("  segment identique a celui du moteur appele directement",
           sortie["resultat"].segment, attendu_moteur.segment)
    r.egal("  sous-segment identique", sortie["resultat"].sous_segment,
           attendu_moteur.sous_segment)
    r.egal("  regle identique", sortie["resultat"].regle_id, attendu_moteur.regle_id)

    # Garantie structurelle du moteur unique : le chatbot delegue, il ne
    # reimplemente pas. (__file__ et non un chemin relatif : le test doit
    # passer quel que soit le repertoire courant.)
    source = open(module_chatbot.__file__, encoding="utf-8").read()
    r.verifier("le chatbot appelle bien le moteur", "self.moteur.segmenter(" in source)

    # ================================================================== #
    # 6bis. SOURCE UNIQUE : les seuils cites sont DERIVES des regles
    # ================================================================== #
    # Les seuils etaient auparavant ecrits en dur dans le texte des reponses,
    # soit une seconde copie des regles. Ce defaut s'etait deja materialise :
    # la correction des seuils MMM du marche TRE (voir _notes_conflits
    # .tre_mmm_vs_revenu_CORRIGE) avait ete appliquee au JSON mais pas au
    # chatbot, qui annoncait 10 mD / 5 mD au lieu de 2,5 mD / 1 mD.
    reponse_tre = chatbot.repondre("Quels sont les seuils TRE ?")["reponse"]
    r.verifier("TRE Premium annonce le seuil REEL du moteur (2.5 mD)",
               "2.5 mD" in reponse_tre, reponse_tre)
    r.verifier("  TRE Potentiel moyen annonce 1 mD", "1 mD" in reponse_tre)
    # Les anciennes valeurs (colonne Revenus : 10 mD / 5 mD) ne doivent plus
    # apparaitre. On teste les LOCUTIONS EXACTES plutot que les nombres isoles :
    # chercher "5 mD" le trouverait dans "2.5 mD" comme dans "25 mD", et meme
    # une borne de mot n'y suffit pas ("2.5 mD" : le point cree une borne juste
    # avant le 5). L'assertion exprime ainsi exactement ce qui est verifie.
    r.verifier("  et n'annonce plus la valeur erronee TRE Premium (colonne Revenus)",
               "MMM >= 10 mD" not in reponse_tre, reponse_tre)
    r.verifier("  ni la valeur erronee TRE Potentiel moyen",
               "MMM >= 5 mD" not in reponse_tre, reponse_tre)

    # Le test decisif : un seuil modifie doit se refleter dans les reponses.
    # C'est ce qui garantit qu'aucune divergence ne peut reapparaitre.
    regles_modifiees = charger_regles()
    for regle in regles_modifiees["marches"]["PART"]["regles"]:
        if regle["id"] == "PART_HDG_FORTUNES":
            regle["conditions"]["vrd"]["min"] = 600_000
    chatbot_modifie = ChatbotExpert(MoteurSegmentation(regles=regles_modifiees))
    reponse_modifiee = chatbot_modifie.repondre("Seuils Fortunes ?")["reponse"]
    r.verifier("un seuil modifie est immediatement reflete dans la reponse",
               "600 mD" in reponse_modifiee, reponse_modifiee)
    r.verifier("  et l'ancienne valeur a disparu", "500 mD" not in reponse_modifiee)

    # Coherence chatbot <-> moteur sur la valeur modifiee : un client a 550 mD
    # n'est plus Fortune, et le chatbot ne doit pas pretendre le contraire.
    res = MoteurSegmentation(regles=regles_modifiees).segmenter(
        {"Marche": "PART", "Age": 45, "MMM": 0, "VRD": 550_000, "Profession": "Autre"}
    )
    r.verifier("  le moteur suit le nouveau seuil", res.sous_segment != "Fortunes")

    # ================================================================== #
    # 7. Absence d'information : le chatbot n'invente jamais
    # ================================================================== #
    for hors_sujet in ("Quelle est la meteo a Tunis ?",
                       "Quel est le taux du credit immobilier ?",
                       "Comment ouvrir un compte ?"):
        r.egal(f"\"{hors_sujet[:36]}...\" -> message d'absence",
               chatbot.repondre(hors_sujet)["reponse"], MESSAGE_ABSENT)

    r.verifier("question vide -> invitation, pas d'erreur",
               chatbot.repondre("")["type"] == "vide")
    r.verifier("question composee d'espaces -> invitation",
               chatbot.repondre("   ")["type"] == "vide")

    # ================================================================== #
    # 8. Toute reponse est sourcee
    # ================================================================== #
    sortie_kb = chatbot.repondre("Quelle est la logique entre MMM et VRD ?")
    r.egal("les reponses de connaissance citent la note", sortie_kb["source"],
           "Note BIAT 2023-06")

    return r.bilan()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
