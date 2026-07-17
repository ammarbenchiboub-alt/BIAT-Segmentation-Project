"""
Authentification simple par compte local (identifiant + mot de passe) avec
roles (Conseiller / Admin / Auditeur).

Implementation volontairement minimale, adaptee a une demonstration de PFE :
les comptes sont stockes localement (auth/utilisateurs.json, auto-cree au
premier lancement, meme principe que core/ml_model/anomaly_pipeline.joblib),
et les mots de passe ne sont JAMAIS stockes en clair (hachage
PBKDF2-HMAC-SHA256 avec sel aleatoire par utilisateur).

Dans un environnement bancaire reel, ce module serait remplace par une
federation d'identite (OIDC/SAML) sur l'Active Directory de la banque, avec
MFA obligatoire pour les roles admin/auditeur -- voir le rapport, section
"Perspectives d'evolution". Ce module reste independant du moteur de
segmentation (core.engine) : aucune dependance dans un sens comme dans
l'autre.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from typing import Any

from . import tentatives

ROLES = ("conseiller", "admin", "auditeur")

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHEMIN_UTILISATEURS = os.path.join(_BASE_DIR, "utilisateurs.json")

_ITERATIONS = 100_000


def _hacher(mot_de_passe: str, sel: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", mot_de_passe.encode("utf-8"), sel, _ITERATIONS).hex()


def _creer_entree(nom: str, mot_de_passe: str, role: str) -> dict:
    sel = secrets.token_bytes(16)
    return {
        "nom": nom,
        "role": role,
        "sel": sel.hex(),
        "hash": _hacher(mot_de_passe, sel),
    }


def _utilisateurs_par_defaut() -> dict:
    """Comptes de demonstration crees au premier lancement.

    Identifiants : conseiller1 / admin1 / admin2 / auditeur1
    Mots de passe : conseiller123 / admin123 / admin456 / auditeur123

    Deux comptes admin sont crees expres : le workflow de double validation
    des seuils (page Parametrage) exige qu'un second administrateur confirme
    ce qu'un premier a propose -- impossible a demontrer avec un seul compte.

    Ces comptes sont destines UNIQUEMENT a la demonstration du PFE. Dans un
    usage reel, ils devraient etre remplaces par de vrais comptes des le
    premier deploiement (voir lister_utilisateurs pour une future page
    d'administration)."""
    return {
        "conseiller1": _creer_entree("Conseiller (demo)", "conseiller123", "conseiller"),
        "admin1": _creer_entree("Administrateur 1 (demo)", "admin123", "admin"),
        "admin2": _creer_entree("Administrateur 2 (demo)", "admin456", "admin"),
        "auditeur1": _creer_entree("Auditeur (demo)", "auditeur123", "auditeur"),
    }


def _charger() -> dict:
    if not os.path.exists(CHEMIN_UTILISATEURS):
        utilisateurs = _utilisateurs_par_defaut()
        _sauvegarder(utilisateurs)
        return utilisateurs
    with open(CHEMIN_UTILISATEURS, encoding="utf-8") as f:
        return json.load(f)


def _sauvegarder(utilisateurs: dict) -> None:
    with open(CHEMIN_UTILISATEURS, "w", encoding="utf-8") as f:
        json.dump(utilisateurs, f, ensure_ascii=False, indent=2)


def verifier_identifiants(identifiant: str, mot_de_passe: str) -> dict[str, Any] | None:
    """Verifie un couple identifiant/mot de passe. NE GERE PAS le verrouillage.

    Renvoie {"identifiant", "nom", "role"} si valide, None sinon. Ne renvoie
    et ne stocke jamais le hash ou le sel au-dela de cette fonction.

    API historique conservee telle quelle (compatibilite). Pour une
    authentification complete avec protection contre la force brute, utiliser
    authentifier() ci-dessous, qui s'appuie sur cette fonction."""
    identifiant = (identifiant or "").strip()
    if not identifiant or not mot_de_passe:
        return None
    utilisateurs = _charger()
    entree = utilisateurs.get(identifiant)
    if not entree:
        # Compte inexistant : on calcule tout de meme un hash factice, de sorte
        # que le temps de reponse soit le meme que pour un compte existant.
        # Sans cela, un attaquant distingue "compte inconnu" (reponse immediate)
        # de "mauvais mot de passe" (~100 000 iterations PBKDF2), et peut ainsi
        # enumerer les comptes valides sans jamais en deviner un mot de passe.
        _hacher(mot_de_passe, b"\x00" * 16)
        return None
    sel = bytes.fromhex(entree["sel"])
    # compare_digest : comparaison a temps constant, insensible a la position
    # du premier octet different (une comparaison '!=' classique s'arrete au
    # premier ecart et fuit donc de l'information par le temps de reponse).
    if not hmac.compare_digest(_hacher(mot_de_passe, sel), entree["hash"]):
        return None
    return {"identifiant": identifiant, "nom": entree["nom"], "role": entree["role"]}


def authentifier(identifiant: str, mot_de_passe: str) -> dict[str, Any]:
    """Authentification complete, protegee contre les attaques par force brute.

    C'est le point d'entree que l'application doit utiliser. Il enchaine :
        1. controle du verrouillage eventuel du compte (avant toute
           verification du mot de passe : un compte verrouille ne doit pas
           pouvoir etre teste, meme avec le bon mot de passe) ;
        2. verification des identifiants (verifier_identifiants) ;
        3. en cas d'echec  : incrementation du compteur + journalisation ;
        4. en cas de succes : remise a zero immediate du compteur.

    Renvoie toujours un dictionnaire (jamais None), decrivant le resultat :
        {
          "succes": bool,
          "utilisateur": dict | None,   # {"identifiant","nom","role"} si succes
          "verrouille": bool,
          "secondes_restantes": int,    # temps restant avant deverrouillage
          "tentatives_restantes": int,  # essais restants avant verrouillage
          "message": str,               # message pret a afficher
        }
    """
    identifiant = (identifiant or "").strip()

    # 1. Le verrouillage prime sur tout le reste.
    verrouille, restant = tentatives.etat_verrouillage(identifiant)
    if verrouille:
        return {
            "succes": False,
            "utilisateur": None,
            "verrouille": True,
            "secondes_restantes": restant,
            "tentatives_restantes": 0,
            "message": (
                f"Compte temporairement verrouille apres {tentatives.MAX_TENTATIVES} "
                f"tentatives infructueuses. Nouvel essai possible dans "
                f"{tentatives.formater_duree(restant)}."
            ),
        }

    # 2. Verification proprement dite.
    utilisateur = verifier_identifiants(identifiant, mot_de_passe)

    # 4. Succes : remise a zero du compteur.
    if utilisateur:
        tentatives.reinitialiser(identifiant)
        return {
            "succes": True,
            "utilisateur": utilisateur,
            "verrouille": False,
            "secondes_restantes": 0,
            "tentatives_restantes": tentatives.MAX_TENTATIVES,
            "message": "Connexion reussie.",
        }

    # 3. Echec : comptabilisation + journalisation.
    verrouille, restant = tentatives.enregistrer_echec(identifiant)
    if verrouille:
        message = (
            f"Identifiant ou mot de passe incorrect. Compte verrouille apres "
            f"{tentatives.MAX_TENTATIVES} tentatives infructueuses : nouvel essai "
            f"possible dans {tentatives.formater_duree(restant)}."
        )
    else:
        restantes = tentatives.tentatives_restantes(identifiant)
        message = (
            f"Identifiant ou mot de passe incorrect. "
            f"{restantes} tentative(s) restante(s) avant verrouillage du compte."
        )
    return {
        "succes": False,
        "utilisateur": None,
        "verrouille": verrouille,
        "secondes_restantes": restant,
        "tentatives_restantes": tentatives.tentatives_restantes(identifiant),
        "message": message,
    }


def lister_utilisateurs() -> list[dict[str, Any]]:
    """Liste les comptes existants (identifiant, nom, role -- jamais les
    secrets), utile pour une future page d'administration ou pour le
    workflow de double validation (verifier qu'un second compte existe)."""
    utilisateurs = _charger()
    return [
        {"identifiant": ident, "nom": e["nom"], "role": e["role"]}
        for ident, e in utilisateurs.items()
    ]
