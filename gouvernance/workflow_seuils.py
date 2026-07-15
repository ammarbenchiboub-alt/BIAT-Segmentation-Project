"""
Workflow de double validation (Maker-Checker) pour les modifications des
regles de segmentation (config/regles_segmentation.json).

Principe : l'administrateur qui PROPOSE un changement de seuils/professions
n'est jamais celui qui l'ACTIVE. Toute proposition doit etre confirmee par un
second compte administrateur avant d'etre appliquee au fichier de regles
officiel -- separation des taches standard en controle interne bancaire.

Ce module ne contient AUCUNE logique de segmentation : il stocke des
propositions de contenu pour regles_segmentation.json et gere leur cycle de
vie (EN_ATTENTE -> VALIDEE / REJETEE). L'ecriture reelle du fichier de regles
est faite par l'appelant (page Parametrage de app.py) une fois la proposition
confirmee, jamais par ce module.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHEMIN_WORKFLOW = os.path.join(_BASE_DIR, "propositions.sqlite3")


def _connexion() -> sqlite3.Connection:
    conn = sqlite3.connect(CHEMIN_WORKFLOW)
    # Voir audit/journal.py : certains environnements de fichiers ne
    # supportent pas le verrouillage par journal SQLite classique sur disque.
    conn.execute("PRAGMA journal_mode=MEMORY")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS propositions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            horodatage_proposition TEXT NOT NULL,
            propose_par TEXT NOT NULL,
            nom_propose_par TEXT NOT NULL,
            description TEXT NOT NULL,
            regles_json TEXT NOT NULL,
            statut TEXT NOT NULL DEFAULT 'EN_ATTENTE',
            confirme_par TEXT,
            nom_confirme_par TEXT,
            horodatage_confirmation TEXT
        )
        """
    )
    return conn


def proposer(utilisateur: dict[str, Any], regles: dict, description: str) -> int:
    """Enregistre une nouvelle proposition de regles, statut EN_ATTENTE.
    N'ecrit jamais dans regles_segmentation.json. Renvoie l'id de la
    proposition."""
    conn = _connexion()
    try:
        horodatage = datetime.now(timezone.utc).isoformat(timespec="seconds")
        curseur = conn.execute(
            "INSERT INTO propositions (horodatage_proposition, propose_par, nom_propose_par, "
            "description, regles_json, statut) VALUES (?, ?, ?, ?, ?, 'EN_ATTENTE')",
            (horodatage, utilisateur["identifiant"], utilisateur["nom"], description,
             json.dumps(regles, ensure_ascii=False)),
        )
        conn.commit()
        return curseur.lastrowid
    finally:
        conn.close()


def lister_en_attente() -> list[dict[str, Any]]:
    conn = _connexion()
    try:
        curseur = conn.execute(
            "SELECT id, horodatage_proposition, propose_par, nom_propose_par, description "
            "FROM propositions WHERE statut='EN_ATTENTE' ORDER BY id DESC"
        )
        colonnes = [d[0] for d in curseur.description]
        return [dict(zip(colonnes, row)) for row in curseur.fetchall()]
    finally:
        conn.close()


def lister_historique(limite: int = 100) -> list[dict[str, Any]]:
    conn = _connexion()
    try:
        curseur = conn.execute(
            "SELECT id, horodatage_proposition, propose_par, description, statut, "
            "confirme_par, horodatage_confirmation FROM propositions "
            "WHERE statut != 'EN_ATTENTE' ORDER BY id DESC LIMIT ?",
            (limite,),
        )
        colonnes = [d[0] for d in curseur.description]
        return [dict(zip(colonnes, row)) for row in curseur.fetchall()]
    finally:
        conn.close()


def obtenir(id_proposition: int) -> dict[str, Any] | None:
    conn = _connexion()
    try:
        curseur = conn.execute("SELECT * FROM propositions WHERE id=?", (id_proposition,))
        colonnes = [d[0] for d in curseur.description]
        ligne = curseur.fetchone()
        return dict(zip(colonnes, ligne)) if ligne else None
    finally:
        conn.close()


def confirmer(id_proposition: int, utilisateur: dict[str, Any]) -> tuple[bool, str, dict | None]:
    """Confirme une proposition EN_ATTENTE.

    Refuse si l'utilisateur qui confirme est le meme que celui qui a propose
    (separation des taches). Renvoie (succes, message, regles_a_appliquer).
    L'ecriture du fichier de regles reste a la charge de l'appelant."""
    proposition = obtenir(id_proposition)
    if not proposition:
        return False, "Proposition introuvable.", None
    if proposition["statut"] != "EN_ATTENTE":
        return False, f"Cette proposition a deja ete traitee (statut : {proposition['statut']}).", None
    if proposition["propose_par"] == utilisateur["identifiant"]:
        return False, "Un meme compte ne peut pas proposer et confirmer le meme changement.", None

    conn = _connexion()
    try:
        horodatage = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn.execute(
            "UPDATE propositions SET statut='VALIDEE', confirme_par=?, nom_confirme_par=?, "
            "horodatage_confirmation=? WHERE id=?",
            (utilisateur["identifiant"], utilisateur["nom"], horodatage, id_proposition),
        )
        conn.commit()
    finally:
        conn.close()
    return True, "Proposition confirmee et appliquee.", json.loads(proposition["regles_json"])


def rejeter(id_proposition: int, utilisateur: dict[str, Any]) -> tuple[bool, str]:
    proposition = obtenir(id_proposition)
    if not proposition:
        return False, "Proposition introuvable."
    if proposition["statut"] != "EN_ATTENTE":
        return False, f"Cette proposition a deja ete traitee (statut : {proposition['statut']})."

    conn = _connexion()
    try:
        horodatage = datetime.now(timezone.utc).isoformat(timespec="seconds")
        conn.execute(
            "UPDATE propositions SET statut='REJETEE', confirme_par=?, nom_confirme_par=?, "
            "horodatage_confirmation=? WHERE id=?",
            (utilisateur["identifiant"], utilisateur["nom"], horodatage, id_proposition),
        )
        conn.commit()
    finally:
        conn.close()
    return True, "Proposition rejetee."
