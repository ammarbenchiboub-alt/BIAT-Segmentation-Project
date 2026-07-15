"""Tests du moteur unique - cas derives directement des seuils de la note.
Seuils en DT (1 mD = 1000 DT)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import segmenter

CAS = [
    ("PART Fortune (VRD>=500mD)", {"Marche":"PART","Age":45,"MMM":0,"VRD":600000,"Profession":"Autre"}, "Haut de Gamme","Fortunes"),
    ("PART Patrimoniaux (VRD 300-500mD)", {"Marche":"PART","Age":45,"MMM":0,"VRD":400000,"Profession":"Autre"}, "Haut de Gamme","Patrimoniaux"),
    ("PART Patrimoniaux (MMM>=10mD)", {"Marche":"PART","Age":45,"MMM":12000,"VRD":0,"Profession":"Autre"}, "Haut de Gamme","Patrimoniaux"),
    ("PART Affluent (VRD 100-300mD)", {"Marche":"PART","Age":45,"MMM":0,"VRD":150000,"Profession":"Autre"}, "Haut de Gamme","Affluent"),
    ("PART Affluent via profession potentiel", {"Marche":"PART","Age":45,"MMM":500,"VRD":0,"Profession":"Magistrats"}, "Haut de Gamme","Affluent"),
    ("PART Classe Moyenne salaries", {"Marche":"PART","Age":45,"MMM":2000,"VRD":0,"Profession":"Autre"}, "Classe Moyenne","Les salaries"),
    ("PART Grand Public", {"Marche":"PART","Age":45,"MMM":300,"VRD":1000,"Profession":"Autre"}, "Grand Public","Particuliers"),
    ("PART Enfant (<=18)", {"Marche":"PART","Age":15,"MMM":0,"VRD":0,"Profession":"Autre"}, "Les Jeunes","Enfants et Eleves"),
    ("PART Etudiant", {"Marche":"PART","Age":24,"MMM":0,"VRD":0,"Profession":"Etudiant"}, "Les Jeunes","Etudiants"),
    ("PART JDA potentiel", {"Marche":"PART","Age":27,"MMM":0,"VRD":0,"Profession":"Ingenieurs"}, "Les Jeunes","JDA a potentiel"),
    ("PART Autres JDA", {"Marche":"PART","Age":27,"MMM":0,"VRD":0,"Profession":"Vendeur"}, "Les Jeunes","Autres JDA"),
    ("PRO Fortune", {"Marche":"PRO","Age":50,"MMM":0,"VRD":700000,"Profession":"Commercant"}, "Haut de Gamme","Fortunes"),
    ("PRO Profession Liberale", {"Marche":"PRO","Age":35,"MMM":0,"VRD":0,"Profession":"Avocats"}, "Haut de Gamme","Professions Liberales"),
    ("PRO Professionnels (montant)", {"Marche":"PRO","Age":50,"MMM":120000,"VRD":0,"Profession":"Commercant"}, "Haut de Gamme","Professionnels"),
    ("PRO Professionnels via profession potentiel hors PL (Magistrats)", {"Marche":"PRO","Age":40,"MMM":500,"VRD":0,"Profession":"Magistrats"}, "Haut de Gamme","Professionnels"),
    ("PRO PL prioritaire meme si aussi a potentiel (Ingenieurs)", {"Marche":"PRO","Age":40,"MMM":500,"VRD":0,"Profession":"Ingenieurs"}, "Haut de Gamme","Professions Liberales"),
    ("PRO Classe Moyenne commercants", {"Marche":"PRO","Age":50,"MMM":8000,"VRD":0,"Profession":"Commercant"}, "Classe Moyenne","Commercants & Artisans"),
    ("PRO Grand Public commercants", {"Marche":"PRO","Age":50,"MMM":90,"VRD":3,"Profession":"Commercant"}, "Grand Public","Commercants & Artisans"),
    ("TRE Premium (profession potentiel)", {"Marche":"TRE","Age":40,"MMM":0,"VRD":60000,"Profession":"Medecins specialistes"}, "Premium","Premium"),
    ("TRE Potentiel moyen", {"Marche":"TRE","Age":40,"MMM":0,"VRD":30000,"Profession":"Autre"}, "Potentiel moyen","Potentiel moyen"),
    ("TRE Faible potentiel", {"Marche":"TRE","Age":40,"MMM":0,"VRD":1000,"Profession":"Autre"}, "Faible potentiel","Faible potentiel"),
    ("TRE Premium via MMM", {"Marche":"TRE","Age":40,"MMM":2500,"VRD":0,"Profession":"Autre"}, "Premium","Premium"),
    ("TRE Potentiel moyen via MMM", {"Marche":"TRE","Age":40,"MMM":1000,"VRD":0,"Profession":"Autre"}, "Potentiel moyen","Potentiel moyen"),
    ("TRE Faible potentiel via MMM", {"Marche":"TRE","Age":40,"MMM":999,"VRD":0,"Profession":"Autre"}, "Faible potentiel","Faible potentiel"),
    ("ENR Premium", {"Marche":"ENR","Age":40,"MMM":0,"VRD":70000,"Profession":"Autre"}, "Premium","Premium"),
    ("ENR Potentiel moyen", {"Marche":"ENR","Age":40,"MMM":0,"VRD":40000,"Profession":"Autre"}, "Potentiel moyen","Potentiel moyen"),
    ("ENR Faible potentiel", {"Marche":"ENR","Age":40,"MMM":0,"VRD":5000,"Profession":"Autre"}, "Faible potentiel","Faible potentiel"),

    ("PART Affluent epargnant exclusif (8e champ actif)",
     {"Marche":"PART","Age":45,"MMM":0,"VRD":150000,"Profession":"Autre","EpargnantDeposantExclusif":True},
     "Haut de Gamme","Epargnants et deposants exclusifs"),
    ("PART Affluent normal si 8e champ absent/False (non-regression)",
     {"Marche":"PART","Age":45,"MMM":0,"VRD":150000,"Profession":"Autre","EpargnantDeposantExclusif":False},
     "Haut de Gamme","Affluent"),
    ("PART Classe Moyenne epargnant exclusif (8e champ actif)",
     {"Marche":"PART","Age":45,"MMM":0,"VRD":50000,"Profession":"Autre","EpargnantDeposantExclusif":True},
     "Classe Moyenne","Epargnants et deposants exclusifs"),
    ("PART Grand Public epargnant exclusif (8e champ actif)",
     {"Marche":"PART","Age":45,"MMM":0,"VRD":1000,"Profession":"Autre","EpargnantDeposantExclusif":True},
     "Grand Public","Epargnants et deposants exclusifs"),
]

def run():
    ok = 0
    for libelle, profil, seg, sous in CAS:
        r = segmenter(profil)
        passe = (r.segment == seg and r.sous_segment == sous)
        ok += passe
        etat = "OK " if passe else "ECHEC"
        print(f"[{etat}] {libelle}")
        if not passe:
            print(f"        attendu: {seg}/{sous}  obtenu: {r.segment}/{r.sous_segment}")
    print(f"\n{ok}/{len(CAS)} cas reussis")
    return ok == len(CAS)

if __name__ == "__main__":
    sys.exit(0 if run() else 1)
