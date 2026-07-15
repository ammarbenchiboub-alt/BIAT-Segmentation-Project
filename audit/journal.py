"""
Journal d'audit persistant et infalsifiable des decisions de segmentation.

Objectif : pouvoir repondre, a tout moment, a la question "qui a segmente quel
profil, quand, avec quel resultat, et avec quelle version des regles ?" --
exigence de base d'un controle interne bancaire.

Principes :
    - Stockage persistant (SQLite, fichier audit/journal.sqlite3) : contrairement
      a st.session_state.historique, ce journal survit a la fermeture de
      l'application.
    - Append-only cote application : ce module n'expose AUCUNE fonction de
      modification ou de suppression d'une entree existante. Seule
      l'insertion est possible.
    - Chainage de hash (façon registre a chaine de blocs simplifie) : chaque
      entree contient le hash de l'entree precedente, et un hash d'elle-meme
      calcule sur tout son contenu. Toute alteration d'une entree passee
      (y compris en modifiant directement le fichier .sqlite3 hors de
      l'application) casse la chaine et devient detectable via
      verifier_integrite().
    - Chaque entree enregistre la version exacte du fichier de regles utilisee
      (hash SHA-256 de regles_segmentation.json au moment de la decision), afin
      de pouvoir justifier une decision meme apres une evolution ulterieure
      des seuils.

Ce module est INDEPENDANT du moteur de segmentation (core.engine) : il ne
fait qu'enregistrer un resultat deja calcule, jamais le contraire. Il est
appele par l'application APRES le moteur, jamais par le moteur lui-meme.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHEMIN_JOURNAL = os.path.join(_BASE_DIR, "journal.sqlite3")

_GENESE = "GENESE"


def _connexion() -> sqlite3.Connection:
    conn = sqlite3.connect(CHEMIN_JOURNAL)
    # Journal de transaction SQLite garde en memoire plutot que sur disque :
    # certains environnements de fichiers synchronises/reseau ne supportent
    # pas correctement le verrouillage par fichier journal classique
    # (erreur "disk I/O error" observee en test). Sans impact reel ici (usage
    # mono-utilisateur, faible volume) : seule la fenetre de tolerance aux
    # pannes en cas de crash exact pendant une ecriture est legerement reduite.
    conn.execute("PRAGMA journal_mode=MEMORY")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            horodatage TEXT NOT NULL,
            identifiant_utilisateur TEXT NOT NULL,
            nom_utilisateur TEXT NOT NULL,
            role_utilisateur TEXT NOT NULL,
            type_action TEXT NOT NULL,
            marche TEXT,
            profil_entree TEXT NOT NULL,
            segment TEXT,
            sous_segment TEXT,
            regle_id TEXT,
            version_regles TEXT NOT NULL,
            hash_precedent TEXT NOT NULL,
            hash_entree TEXT NOT NULL
        )
        """
    )
    return conn


def _hash_regles_actives() -> str:
    """Empreinte SHA-256 du fichier de regles au moment de l'enregistrement.
    Permet de savoir exactement quelle version des seuils a produit une
    decision donnee, meme si les seuils sont modifies plus tard."""
    from core.rules_loader import CHEMIN_REGLES

    with open(CHEMIN_REGLES, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def _derniere_entree(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT hash_entree FROM journal ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else _GENESE


def _calculer_hash(champs: dict, hash_precedent: str) -> str:
    contenu = json.dumps(champs, sort_keys=True, ensure_ascii=False) + hash_precedent
    return hashlib.sha256(contenu.encode("utf-8")).hexdigest()


def enregistrer(
    type_action: str,
    utilisateur: dict[str, Any],
    profil: dict[str, Any],
    segment: str | None,
    sous_segment: str | None,
    regle_id: str | None,
) -> None:
    """Ajoute une entree au journal. Ne modifie et ne supprime jamais une
    entree existante (append-only)."""
    horodatage = datetime.now(timezone.utc).isoformat(timespec="seconds")
    version_regles = _hash_regles_actives()

    conn = _connexion()
    try:
        hash_precedent = _derniere_entree(conn)
        champs = {
            "horodatage": horodatage,
            "identifiant_utilisateur": utilisateur.get("identifiant", "?"),
            "nom_utilisateur": utilisateur.get("nom", "?"),
            "role_utilisateur": utilisateur.get("role", "?"),
            "type_action": type_action,
            "marche": profil.get("Marche"),
            "profil_entree": json.dumps(profil, ensure_ascii=False, sort_keys=True),
            "segment": segment,
            "sous_segment": sous_segment,
            "regle_id": regle_id,
            "version_regles": version_regles,
        }
        hash_entree = _calculer_hash(champs, hash_precedent)
        conn.execute(
            """
            INSERT INTO journal (
                horodatage, identifiant_utilisateur, nom_utilisateur, role_utilisateur,
                type_action, marche, profil_entree, segment, sous_segment, regle_id,
                version_regles, hash_precedent, hash_entree
            ) VALUES (:horodatage, :identifiant_utilisateur, :nom_utilisateur, :role_utilisateur,
                      :type_action, :marche, :profil_entree, :segment, :sous_segment, :regle_id,
                      :version_regles, :hash_precedent, :hash_entree)
            """,
            {**champs, "hash_precedent": hash_precedent, "hash_entree": hash_entree},
        )
        conn.commit()
    finally:
        conn.close()


def enregistrer_lot(
    type_action: str,
    utilisateur: dict[str, Any],
    lignes: list[dict[str, Any]],
) -> int:
    """Enregistre plusieurs decisions d'un coup (import de masse). Chaque
    ligne du lot devient sa propre entree chainee dans le journal, pour
    garder une tracabilite ligne par ligne identique a la simulation
    individuelle. Renvoie le nombre d'entrees ajoutees."""
    for ligne in lignes:
        enregistrer(
            type_action,
            utilisateur,
            {k: v for k, v in ligne.items()
             if k in ("Marche", "Profession", "Age", "MMM", "VRD", "Nationalite", "Residence",
                      "EpargnantDeposantExclusif")},
            ligne.get("Segment"),
            ligne.get("Sous_segment"),
            ligne.get("Regle") or ligne.get("Regle_ID"),
        )
    return len(lignes)


def lister(limite: int = 500) -> list[dict[str, Any]]:
    """Renvoie les `limite` entrees les plus recentes (lecture seule)."""
    conn = _connexion()
    try:
        curseur = conn.execute(
            "SELECT id, horodatage, identifiant_utilisateur, nom_utilisateur, role_utilisateur, "
            "type_action, marche, segment, sous_segment, regle_id, version_regles "
            "FROM journal ORDER BY id DESC LIMIT ?",
            (limite,),
        )
        colonnes = [d[0] for d in curseur.description]
        return [dict(zip(colonnes, row)) for row in curseur.fetchall()]
    finally:
        conn.close()


def lister_profils(limite: int = 2000) -> list[dict[str, Any]]:
    """Renvoie les profils client (deja segmentes) enregistres dans le
    journal, reconstruits a partir de profil_entree. Utilise UNIQUEMENT pour
    la simulation d'impact d'un changement de seuils (page Parametrage) :
    permet de rejouer de vraies decisions passees a travers un jeu de regles
    propose, sans jamais modifier le journal lui-meme (lecture seule)."""
    conn = _connexion()
    try:
        curseur = conn.execute(
            "SELECT profil_entree, segment, sous_segment, regle_id "
            "FROM journal ORDER BY id DESC LIMIT ?",
            (limite,),
        )
        resultats = []
        for profil_entree, segment, sous_segment, regle_id in curseur.fetchall():
            try:
                profil = json.loads(profil_entree)
            except (TypeError, ValueError):
                continue
            profil["_Segment_journal"] = segment
            profil["_Sous_segment_journal"] = sous_segment
            profil["_Regle_journal"] = regle_id
            resultats.append(profil)
        return resultats
    finally:
        conn.close()


def compter() -> int:
    conn = _connexion()
    try:
        return conn.execute("SELECT COUNT(*) FROM journal").fetchone()[0]
    finally:
        conn.close()


def verifier_integrite() -> tuple[bool, str]:
    """Recalcule la chaine de hash sur l'ensemble du journal et verifie
    qu'aucune entree n'a ete modifiee ou supprimee hors de ce module. Renvoie
    (True, message) si la chaine est intacte, (False, message) sinon."""
    conn = _connexion()
    try:
        lignes = conn.execute(
            "SELECT horodatage, identifiant_utilisateur, nom_utilisateur, role_utilisateur, "
            "type_action, marche, profil_entree, segment, sous_segment, regle_id, "
            "version_regles, hash_precedent, hash_entree FROM journal ORDER BY id ASC"
        ).fetchall()
    finally:
        conn.close()

    hash_attendu = _GENESE
    for i, ligne in enumerate(lignes, start=1):
        (horodatage, identifiant_utilisateur, nom_utilisateur, role_utilisateur,
         type_action, marche, profil_entree, segment, sous_segment, regle_id,
         version_regles, hash_precedent, hash_entree) = ligne

        if hash_precedent != hash_attendu:
            return False, f"Chaine rompue a l'entree {i} : hash_precedent ne correspond pas."

        champs = {
            "horodatage": horodatage,
            "identifiant_utilisateur": identifiant_utilisateur,
            "nom_utilisateur": nom_utilisateur,
            "role_utilisateur": role_utilisateur,
            "type_action": type_action,
            "marche": marche,
            "profil_entree": profil_entree,
            "segment": segment,
            "sous_segment": sous_segment,
            "regle_id": regle_id,
            "version_regles": version_regles,
        }
        recalcule = _calculer_hash(champs, hash_precedent)
        if recalcule != hash_entree:
            return False, f"Entree {i} modifiee : le hash ne correspond plus a son contenu."

        hash_attendu = hash_entree

    return True, f"Journal intact : {len(lignes)} entree(s) verifiee(s), chaine ininterrompue."
