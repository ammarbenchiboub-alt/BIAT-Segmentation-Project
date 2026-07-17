"""Tests d'integrite du journal d'audit.

Verifie que verifier_integrite() detecte bien les quatre familles
d'alteration, y compris le TRONQUAGE DE FIN qui echappait au seul chainage de
hash (motif de l'ajout de l'ancre externe) :

    - modification d'une entree            -> hash de l'entree
    - reorganisation des entrees           -> chainage hash_precedent
    - suppression au milieu                -> chainage hash_precedent
    - suppression des dernieres entrees    -> ancre externe
    - ajout d'entrees hors application     -> ancre externe
    - tronquage + ancre "reparee"          -> hash de fin de l'ancre
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys

from _outils import ModulesRediriges, Resultats, dossier_temporaire

from audit import journal

UTILISATEUR = {"identifiant": "admin1", "nom": "Admin 1", "role": "admin"}


def _remplir(n: int = 5) -> None:
    for i in range(n):
        journal.enregistrer(
            "SIMULATION_INDIVIDUELLE", UTILISATEUR,
            {"Marche": "PART", "Age": 30 + i, "MMM": 1000 * i, "VRD": 0},
            "Classe Moyenne", "Les salaries", "PART_CM_SALARIES",
        )


def _sql(requete: str) -> None:
    conn = sqlite3.connect(journal.CHEMIN_JOURNAL)
    conn.executescript(requete)
    conn.commit()
    conn.close()


def run() -> bool:
    r = Resultats("integrite du journal d'audit")
    tmp = dossier_temporaire()

    with ModulesRediriges(
        (journal, "CHEMIN_JOURNAL", os.path.join(tmp, "journal.sqlite3")),
        (journal, "CHEMIN_ANCRE", os.path.join(tmp, "ancre.json")),
    ):
        _remplir(5)

        # --- Etat nominal --------------------------------------------------
        ok, msg = journal.verifier_integrite()
        r.verifier("journal intact -> integrite confirmee", ok, msg)
        r.egal("5 entrees enregistrees", journal.compter(), 5)
        r.verifier("l'ancre externe existe", os.path.exists(journal.CHEMIN_ANCRE))
        ancre = json.load(open(journal.CHEMIN_ANCRE, encoding="utf-8"))
        r.egal("  l'ancre connait le nombre d'entrees", ancre["nombre_entrees"], 5)
        r.verifier("  l'ancre est hors de journal.sqlite3",
                   os.path.dirname(journal.CHEMIN_ANCRE) == os.path.dirname(journal.CHEMIN_JOURNAL)
                   and journal.CHEMIN_ANCRE != journal.CHEMIN_JOURNAL)

        # --- Durabilite (item 6) ------------------------------------------
        conn = sqlite3.connect(journal.CHEMIN_JOURNAL)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        r.egal("journal_mode durable (delete, plus 'memory')", mode.lower(), "delete")

        # Sauvegarde de l'etat sain pour restaurer entre chaque attaque.
        sain_db, sain_ancre = journal.CHEMIN_JOURNAL + ".sain", journal.CHEMIN_ANCRE + ".sain"
        shutil.copy(journal.CHEMIN_JOURNAL, sain_db)
        shutil.copy(journal.CHEMIN_ANCRE, sain_ancre)

        def restaurer():
            shutil.copy(sain_db, journal.CHEMIN_JOURNAL)
            shutil.copy(sain_ancre, journal.CHEMIN_ANCRE)

        # --- Attaque 1 : modification d'une entree -------------------------
        _sql("UPDATE journal SET segment='Haut de Gamme' WHERE id=2;")
        ok, msg = journal.verifier_integrite()
        r.verifier("modification d'une entree -> detectee", not ok, msg)
        r.verifier("  message explicite ('modifiee')", "modifiee" in msg.lower())
        restaurer()

        # --- Attaque 2 : suppression au milieu -----------------------------
        _sql("DELETE FROM journal WHERE id=3;")
        ok, msg = journal.verifier_integrite()
        r.verifier("suppression au milieu -> detectee", not ok, msg)
        restaurer()

        # --- Attaque 3 : reorganisation ------------------------------------
        _sql("""
            UPDATE journal SET id=99 WHERE id=2;
            UPDATE journal SET id=2  WHERE id=3;
            UPDATE journal SET id=3  WHERE id=99;
        """)
        ok, msg = journal.verifier_integrite()
        r.verifier("reorganisation des entrees -> detectee", not ok, msg)
        r.verifier("  message explicite ('chaine rompue')", "chaine rompue" in msg.lower())
        restaurer()

        # --- Attaque 4 : TRONQUAGE DE FIN (le cas qui echappait avant) -----
        _sql("DELETE FROM journal WHERE id>=4;")
        ok, msg = journal.verifier_integrite()
        r.verifier("TRONQUAGE DE FIN -> detecte grace a l'ancre", not ok, msg)
        r.verifier("  message chiffre les entrees manquantes", "2 entree(s) manquante(s)" in msg)
        restaurer()

        # --- Attaque 5 : tronquage + ancre "reparee" par l'attaquant -------
        # L'attaquant supprime 2 entrees ET corrige le compteur de l'ancre,
        # mais ne peut pas recalculer le hash de fin sans le contenu supprime.
        _sql("DELETE FROM journal WHERE id>=4;")
        ancre = json.load(open(journal.CHEMIN_ANCRE, encoding="utf-8"))
        ancre["nombre_entrees"] = 3
        json.dump(ancre, open(journal.CHEMIN_ANCRE, "w", encoding="utf-8"))
        ok, msg = journal.verifier_integrite()
        r.verifier("tronquage + compteur d'ancre falsifie -> detecte par le hash de fin",
                   not ok, msg)
        restaurer()

        # --- Attaque 6 : ajout d'entrees hors application -------------------
        _sql("""
            INSERT INTO journal (horodatage, identifiant_utilisateur, nom_utilisateur,
                role_utilisateur, type_action, marche, profil_entree, segment,
                sous_segment, regle_id, version_regles, hash_precedent, hash_entree)
            VALUES ('2026-01-01T00:00:00+00:00','pirate','Pirate','admin','FAUX','PART',
                    '{}','Haut de Gamme','Fortunes','X','0','0','0');
        """)
        ok, msg = journal.verifier_integrite()
        r.verifier("ajout d'une entree hors application -> detecte", not ok, msg)
        restaurer()

        # --- Attaque 7 : suppression de l'ancre ----------------------------
        os.remove(journal.CHEMIN_ANCRE)
        ok, msg = journal.verifier_integrite()
        r.verifier("ancre supprimee -> signalee, puis reinitialisee", ok and "Ancre" in msg, msg)
        r.verifier("  l'ancre est recreee", os.path.exists(journal.CHEMIN_ANCRE))
        restaurer()

        # --- Attaque 8 : ancre corrompue -----------------------------------
        open(journal.CHEMIN_ANCRE, "w").write("{ ceci n'est pas du json")
        ok, msg = journal.verifier_integrite()
        r.verifier("ancre corrompue -> refus de conclure a l'integrite", not ok, msg)
        restaurer()

        # --- Retour a l'etat sain ------------------------------------------
        ok, msg = journal.verifier_integrite()
        r.verifier("apres restauration -> journal a nouveau declare intact", ok, msg)

        # --- Append-only : aucune API de suppression/modification ----------
        interdits = [n for n in ("supprimer", "modifier", "effacer", "vider", "update")
                     if hasattr(journal, n)]
        r.egal("aucune fonction de suppression/modification exposee", interdits, [])

        # --- L'ajout continue de fonctionner apres verification ------------
        _remplir(2)
        ok, msg = journal.verifier_integrite()
        r.verifier("ajout apres verification -> chaine et ancre toujours coherentes", ok, msg)
        r.egal("  nombre d'entrees mis a jour", journal.compter(), 7)

        # --- La version des regles est tracee ------------------------------
        entrees = journal.lister()
        r.verifier("chaque entree trace la version des regles utilisee",
                   all(e["version_regles"] for e in entrees))

        # --- lister_profils reste en lecture seule -------------------------
        avant = journal.compter()
        journal.lister_profils()
        r.egal("lister_profils ne modifie pas le journal", journal.compter(), avant)

    return r.bilan()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
