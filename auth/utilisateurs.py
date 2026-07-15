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
import json
import os
import secrets
from typing import Any

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
    """Verifie un couple identifiant/mot de passe.

    Renvoie {"identifiant", "nom", "role"} si valide, None sinon. Ne renvoie
    et ne stocke jamais le hash ou le sel au-dela de cette fonction."""
    identifiant = (identifiant or "").strip()
    if not identifiant or not mot_de_passe:
        return None
    utilisateurs = _charger()
    entree = utilisateurs.get(identifiant)
    if not entree:
        return None
    sel = bytes.fromhex(entree["sel"])
    if _hacher(mot_de_passe, sel) != entree["hash"]:
        return None
    return {"identifiant": identifiant, "nom": entree["nom"], "role": entree["role"]}


def lister_utilisateurs() -> list[dict[str, Any]]:
    """Liste les comptes existants (identifiant, nom, role -- jamais les
    secrets), utile pour une future page d'administration ou pour le
    workflow de double validation (verifier qu'un second compte existe)."""
    utilisateurs = _charger()
    return [
        {"identifiant": ident, "nom": e["nom"], "role": e["role"]}
        for ident, e in utilisateurs.items()
    ]
