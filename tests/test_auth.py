"""Tests de l'authentification et de la protection contre la force brute.

Couvre : hachage des mots de passe, verification des identifiants, comptage
des echecs, verrouillage, deverrouillage automatique, remise a zero apres
succes, et journalisation des tentatives.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

from _outils import ModulesRediriges, Resultats, dossier_temporaire

from auth import tentatives, utilisateurs


def _forcer_expiration(identifiant: str) -> None:
    """Place la fin de verrouillage dans le passe, pour tester le
    deverrouillage automatique sans attendre reellement 15 minutes."""
    passe = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    conn = sqlite3.connect(tentatives.CHEMIN_TENTATIVES)
    conn.execute("UPDATE etat SET verrouille_jusqu_a=? WHERE identifiant=?", (passe, identifiant))
    conn.commit()
    conn.close()


def run() -> bool:
    r = Resultats("authentification & force brute")
    tmp = dossier_temporaire()

    with ModulesRediriges(
        (utilisateurs, "CHEMIN_UTILISATEURS", os.path.join(tmp, "utilisateurs.json")),
        (tentatives, "CHEMIN_TENTATIVES", os.path.join(tmp, "tentatives.sqlite3")),
        (tentatives, "MAX_TENTATIVES", 5),
        (tentatives, "DUREE_VERROUILLAGE_MINUTES", 15),
    ):
        # --- Authentification de base -------------------------------------
        u = utilisateurs.verifier_identifiants("admin1", "admin123")
        r.verifier("identifiants valides -> utilisateur renvoye", u is not None)
        r.egal("  role correct", u["role"] if u else None, "admin")
        r.verifier("mot de passe errone -> None",
                   utilisateurs.verifier_identifiants("admin1", "mauvais") is None)
        r.verifier("compte inexistant -> None",
                   utilisateurs.verifier_identifiants("fantome", "x") is None)
        r.verifier("identifiant vide -> None",
                   utilisateurs.verifier_identifiants("", "x") is None)
        r.verifier("mot de passe vide -> None",
                   utilisateurs.verifier_identifiants("admin1", "") is None)

        # --- Les mots de passe ne sont jamais stockes en clair -------------
        contenu = open(utilisateurs.CHEMIN_UTILISATEURS, encoding="utf-8").read()
        r.verifier("aucun mot de passe en clair dans utilisateurs.json",
                   "admin123" not in contenu and "conseiller123" not in contenu)
        r.verifier("sel different par utilisateur",
                   len({e["sel"] for e in __import__("json").loads(contenu).values()}) == 4)

        # --- Comptage des echecs ------------------------------------------
        for i in range(1, 5):
            res = utilisateurs.authentifier("admin1", "mauvais")
            r.verifier(f"echec {i}/5 -> refuse, pas encore verrouille",
                       not res["succes"] and not res["verrouille"])
            r.egal(f"  tentatives restantes apres echec {i}", res["tentatives_restantes"], 5 - i)

        # --- 5e echec : verrouillage --------------------------------------
        res = utilisateurs.authentifier("admin1", "mauvais")
        r.verifier("5e echec -> compte verrouille", res["verrouille"])
        r.verifier("  temps restant annonce (<= 15 min)",
                   0 < res["secondes_restantes"] <= 15 * 60)
        r.verifier("  message mentionne le temps restant", "min" in res["message"])

        # --- Verrouillage effectif meme avec le BON mot de passe ----------
        res = utilisateurs.authentifier("admin1", "admin123")
        r.verifier("compte verrouille : le bon mot de passe est refuse aussi",
                   not res["succes"] and res["verrouille"])

        # --- Isolation entre comptes --------------------------------------
        res = utilisateurs.authentifier("admin2", "admin456")
        r.verifier("verrouillage par utilisateur : admin2 non affecte", res["succes"])

        # --- Deverrouillage automatique -----------------------------------
        _forcer_expiration("admin1")
        verrouille, restant = tentatives.etat_verrouillage("admin1")
        r.verifier("deverrouillage automatique une fois la duree ecoulee",
                   not verrouille and restant == 0)
        res = utilisateurs.authentifier("admin1", "admin123")
        r.verifier("  connexion a nouveau possible apres expiration", res["succes"])

        # --- Remise a zero apres succes -----------------------------------
        r.egal("compteur remis a zero apres connexion reussie",
               tentatives.echecs_consecutifs("admin1"), 0)
        utilisateurs.authentifier("admin1", "mauvais")
        utilisateurs.authentifier("admin1", "mauvais")
        r.egal("  2 nouveaux echecs comptabilises",
               tentatives.echecs_consecutifs("admin1"), 2)
        utilisateurs.authentifier("admin1", "admin123")
        r.egal("  succes -> compteur a nouveau a zero",
               tentatives.echecs_consecutifs("admin1"), 0)

        # --- Anti-enumeration : un compte inexistant se verrouille aussi ---
        for _ in range(5):
            res = utilisateurs.authentifier("compte_inexistant", "x")
        r.verifier("compte inexistant verrouille aussi (anti-enumeration)",
                   res["verrouille"])

        # --- Journalisation des echecs ------------------------------------
        echecs = tentatives.lister_echecs()
        r.verifier("les tentatives echouees sont journalisees", len(echecs) > 0)
        r.verifier("  le journal contient l'identifiant vise",
                   any(e["identifiant"] == "admin1" for e in echecs))
        r.verifier("  le declenchement du verrouillage est trace",
                   any(e["verrouillage_declenche"] == 1 for e in echecs))
        r.verifier("  le journal survit a une connexion reussie",
                   any(e["identifiant"] == "admin1" for e in tentatives.lister_echecs()))

        # --- Configurabilite ----------------------------------------------
        with ModulesRediriges((tentatives, "MAX_TENTATIVES", 2)):
            tentatives.reinitialiser("configtest")
            utilisateurs.authentifier("configtest", "x")
            res = utilisateurs.authentifier("configtest", "x")
            r.verifier("MAX_TENTATIVES configurable (2 -> verrouillage au 2e echec)",
                       res["verrouille"])

    return r.bilan()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
