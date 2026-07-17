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
import threading
from datetime import datetime, timezone
from typing import Any

from commun import connexion_durable

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHEMIN_WORKFLOW = os.path.join(_BASE_DIR, "propositions.sqlite3")

# Serialise le cycle "lire le statut -> verifier -> ecrire le statut" de
# confirmer()/rejeter(). Sans lui, deux administrateurs cliquant "Confirmer" au
# meme instant lisent tous deux le statut EN_ATTENTE et valident la meme
# proposition deux fois -- avec, a la clef, deux applications du meme
# changement et deux entrees d'audit contradictoires.
_VERROU_STATUT = threading.Lock()


def _connexion() -> sqlite3.Connection:
    # Configuration de durabilite centralisee (commun/base_sqlite.py).
    # Ce module etait reste en journal_mode=MEMORY alors que les autres bases
    # avaient ete durcies : les propositions en attente n'etaient donc pas
    # durables, et toute ecriture concurrente echouait faute de timeout.
    conn = connexion_durable(CHEMIN_WORKFLOW)
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
    L'ecriture du fichier de regles reste a la charge de l'appelant.

    Le controle du statut et sa mise a jour sont INDIVISIBLES (verrou de thread
    + BEGIN IMMEDIATE). Auparavant, la lecture (obtenir) et l'ecriture (UPDATE)
    etaient deux transactions distinctes : deux administrateurs cliquant
    "Confirmer" au meme instant lisaient tous deux le statut EN_ATTENTE et
    validaient la meme proposition -- le changement etait alors applique deux
    fois, avec deux versions archivees et deux entrees d'audit pour un seul
    acte de gouvernance. La clause `WHERE ... AND statut='EN_ATTENTE'` ajoute
    une seconde barriere : meme sans le verrou, le second UPDATE ne toucherait
    aucune ligne."""
    with _VERROU_STATUT:
        conn = _connexion()
        try:
            conn.execute("BEGIN IMMEDIATE")
            ligne = conn.execute(
                "SELECT statut, propose_par, regles_json FROM propositions WHERE id=?",
                (id_proposition,),
            ).fetchone()
            if not ligne:
                conn.rollback()
                return False, "Proposition introuvable.", None
            statut, propose_par, regles_json = ligne
            if statut != "EN_ATTENTE":
                conn.rollback()
                return False, f"Cette proposition a deja ete traitee (statut : {statut}).", None
            if propose_par == utilisateur["identifiant"]:
                conn.rollback()
                return False, "Un meme compte ne peut pas proposer et confirmer le meme changement.", None

            horodatage = datetime.now(timezone.utc).isoformat(timespec="seconds")
            curseur = conn.execute(
                "UPDATE propositions SET statut='VALIDEE', confirme_par=?, nom_confirme_par=?, "
                "horodatage_confirmation=? WHERE id=? AND statut='EN_ATTENTE'",
                (utilisateur["identifiant"], utilisateur["nom"], horodatage, id_proposition),
            )
            if curseur.rowcount != 1:  # pragma: no cover - defense en profondeur
                conn.rollback()
                return False, "Cette proposition vient d'etre traitee par un autre administrateur.", None
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    return True, "Proposition confirmee et appliquee.", json.loads(regles_json)


def rouvrir(id_proposition: int) -> None:
    """Repasse une proposition VALIDEE a l'etat EN_ATTENTE.

    USAGE STRICTEMENT RESERVE au rollback transactionnel (voir
    gouvernance/application_regles.py) : si une etape POSTERIEURE a la
    confirmation echoue (ecriture du fichier de regles, versionnement,
    journalisation), la confirmation doit etre annulee pour que l'ensemble de
    l'operation soit sans effet -- une proposition marquee VALIDEE alors que
    les regles n'ont pas ete appliquees serait un mensonge de l'historique.

    N'est volontairement PAS exposee dans gouvernance/__init__.py : ce n'est
    pas une action metier offerte a l'utilisateur, et elle ne doit jamais
    servir a "devalider" une proposition reellement appliquee."""
    conn = _connexion()
    try:
        conn.execute(
            "UPDATE propositions SET statut='EN_ATTENTE', confirme_par=NULL, "
            "nom_confirme_par=NULL, horodatage_confirmation=NULL WHERE id=?",
            (id_proposition,),
        )
        conn.commit()
    finally:
        conn.close()


def rejeter(id_proposition: int, utilisateur: dict[str, Any]) -> tuple[bool, str]:
    """Rejette une proposition EN_ATTENTE.

    Meme protection que confirmer() contre les traitements concurrents : le
    controle du statut et sa mise a jour forment une seule transaction."""
    with _VERROU_STATUT:
        conn = _connexion()
        try:
            conn.execute("BEGIN IMMEDIATE")
            ligne = conn.execute(
                "SELECT statut FROM propositions WHERE id=?", (id_proposition,)
            ).fetchone()
            if not ligne:
                conn.rollback()
                return False, "Proposition introuvable."
            if ligne[0] != "EN_ATTENTE":
                conn.rollback()
                return False, f"Cette proposition a deja ete traitee (statut : {ligne[0]})."

            horodatage = datetime.now(timezone.utc).isoformat(timespec="seconds")
            curseur = conn.execute(
                "UPDATE propositions SET statut='REJETEE', confirme_par=?, nom_confirme_par=?, "
                "horodatage_confirmation=? WHERE id=? AND statut='EN_ATTENTE'",
                (utilisateur["identifiant"], utilisateur["nom"], horodatage, id_proposition),
            )
            if curseur.rowcount != 1:  # pragma: no cover - defense en profondeur
                conn.rollback()
                return False, "Cette proposition vient d'etre traitee par un autre administrateur."
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    return True, "Proposition rejetee."
