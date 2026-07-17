"""
Protection contre les attaques par force brute sur l'authentification.

Principe : au-dela d'un nombre configurable d'echecs consecutifs, le compte
concerne est verrouille pendant une duree configurable. Le deverrouillage est
AUTOMATIQUE (aucune intervention d'un administrateur n'est requise) : il suffit
que la duree de verrouillage soit ecoulee. Un succes remet immediatement le
compteur a zero.

Choix de conception importants
------------------------------
1. Verrouillage PAR IDENTIFIANT (et non par adresse IP). Streamlit s'execute
   ici derriere un poste unique / un reverse proxy interne : l'IP vue par
   l'application n'est pas fiable et serait souvent la meme pour tous. Le
   compte est le seul discriminant robuste dans ce contexte.

2. Le verrouillage s'applique a TOUT identifiant saisi, y compris un
   identifiant INEXISTANT. C'est volontaire : ne verrouiller que les comptes
   existants permettrait a un attaquant de deduire quels comptes existent en
   observant lesquels se verrouillent (enumeration d'utilisateurs).

3. Stockage persistant (SQLite, auth/tentatives.sqlite3) plutot qu'en memoire
   de session : un compteur en st.session_state serait remis a zero en
   rouvrant simplement un onglet, ce qui annulerait toute la protection.

4. Les echecs sont journalises (table `echecs`) avec leur horodatage, ce qui
   permet de constater a posteriori une tentative d'intrusion.

Ce module est INDEPENDANT du moteur de segmentation (core.engine) : aucune
dependance dans un sens comme dans l'autre.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHEMIN_TENTATIVES = os.path.join(_BASE_DIR, "tentatives.sqlite3")

# --------------------------------------------------------------------------- #
# Parametres configurables
# --------------------------------------------------------------------------- #
# Surchargeables par variable d'environnement au deploiement, sans toucher au
# code (ex : BIAT_MAX_TENTATIVES=3). Les tests les surchargent directement en
# reaffectant les attributs du module.
MAX_TENTATIVES = int(os.environ.get("BIAT_MAX_TENTATIVES", "5"))
DUREE_VERROUILLAGE_MINUTES = int(os.environ.get("BIAT_VERROUILLAGE_MINUTES", "15"))


def _connexion() -> sqlite3.Connection:
    conn = sqlite3.connect(CHEMIN_TENTATIVES)
    # Meme compromis durabilite/portabilite que audit/journal.py : le journal
    # de rollback reste sur disque (DELETE) et chaque commit est fsync
    # (synchronous=FULL), pour qu'un verrou ne puisse pas disparaitre a la
    # faveur d'un crash -- ce qui offrirait a un attaquant un moyen trivial de
    # remettre le compteur a zero.
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("PRAGMA synchronous=FULL")
    except sqlite3.DatabaseError:  # pragma: no cover - environnement degrade
        conn.execute("PRAGMA journal_mode=MEMORY")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS etat (
            identifiant TEXT PRIMARY KEY,
            echecs_consecutifs INTEGER NOT NULL DEFAULT 0,
            verrouille_jusqu_a TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS echecs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            identifiant TEXT NOT NULL,
            horodatage TEXT NOT NULL,
            echecs_consecutifs INTEGER NOT NULL,
            verrouillage_declenche INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    return conn


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


def _lire_etat(conn: sqlite3.Connection, identifiant: str) -> tuple[int, datetime | None]:
    ligne = conn.execute(
        "SELECT echecs_consecutifs, verrouille_jusqu_a FROM etat WHERE identifiant=?",
        (identifiant,),
    ).fetchone()
    if not ligne:
        return 0, None
    echecs, jusqu_a = ligne
    if not jusqu_a:
        return echecs, None
    try:
        return echecs, datetime.fromisoformat(jusqu_a)
    except ValueError:  # pragma: no cover - donnee corrompue
        return echecs, None


def etat_verrouillage(identifiant: str) -> tuple[bool, int]:
    """Renvoie (verrouille, secondes_restantes) pour un identifiant.

    Le deverrouillage est automatique : des que l'instant de fin de
    verrouillage est passe, la fonction renvoie (False, 0) sans qu'aucune
    action d'administration n'ait ete necessaire.
    """
    identifiant = (identifiant or "").strip()
    if not identifiant:
        return False, 0
    conn = _connexion()
    try:
        _, jusqu_a = _lire_etat(conn, identifiant)
    finally:
        conn.close()
    if jusqu_a is None:
        return False, 0
    restant = (jusqu_a - _maintenant()).total_seconds()
    if restant <= 0:
        return False, 0
    return True, int(restant) + 1  # arrondi au superieur : 0.2 s restante -> 1 s


def enregistrer_echec(identifiant: str) -> tuple[bool, int]:
    """Comptabilise un echec d'authentification et journalise la tentative.

    Renvoie (verrouille, secondes_restantes) APRES prise en compte de cet
    echec : le verrouillage prend donc effet des le Nieme echec, sans attendre
    une tentative supplementaire.
    """
    identifiant = (identifiant or "").strip()
    if not identifiant:
        return False, 0

    conn = _connexion()
    try:
        echecs, jusqu_a = _lire_etat(conn, identifiant)

        # Un verrouillage expire remet le compteur a zero : les echecs d'une
        # salve deja sanctionnee ne doivent pas s'additionner a la suivante,
        # sinon un compte finirait verrouille a vie apres quelques erreurs de
        # frappe espacees dans le temps.
        if jusqu_a is not None and (jusqu_a - _maintenant()).total_seconds() <= 0:
            echecs = 0
            jusqu_a = None

        echecs += 1
        declenche = 0
        if echecs >= MAX_TENTATIVES:
            jusqu_a = _maintenant() + timedelta(minutes=DUREE_VERROUILLAGE_MINUTES)
            declenche = 1

        conn.execute(
            "INSERT INTO etat (identifiant, echecs_consecutifs, verrouille_jusqu_a) "
            "VALUES (?, ?, ?) ON CONFLICT(identifiant) DO UPDATE SET "
            "echecs_consecutifs=excluded.echecs_consecutifs, "
            "verrouille_jusqu_a=excluded.verrouille_jusqu_a",
            (identifiant, echecs, jusqu_a.isoformat() if jusqu_a else None),
        )
        conn.execute(
            "INSERT INTO echecs (identifiant, horodatage, echecs_consecutifs, "
            "verrouillage_declenche) VALUES (?, ?, ?, ?)",
            (identifiant, _maintenant().isoformat(timespec="seconds"), echecs, declenche),
        )
        conn.commit()
    finally:
        conn.close()

    return etat_verrouillage(identifiant)


def reinitialiser(identifiant: str) -> None:
    """Remet le compteur d'echecs a zero (a appeler apres une connexion
    reussie). Ne purge pas la table `echecs` : l'historique des tentatives
    echouees reste consultable meme apres une connexion reussie."""
    identifiant = (identifiant or "").strip()
    if not identifiant:
        return
    conn = _connexion()
    try:
        conn.execute("DELETE FROM etat WHERE identifiant=?", (identifiant,))
        conn.commit()
    finally:
        conn.close()


def echecs_consecutifs(identifiant: str) -> int:
    """Nombre d'echecs consecutifs actuellement comptabilises."""
    identifiant = (identifiant or "").strip()
    if not identifiant:
        return 0
    conn = _connexion()
    try:
        echecs, _ = _lire_etat(conn, identifiant)
        return echecs
    finally:
        conn.close()


def tentatives_restantes(identifiant: str) -> int:
    """Nombre d'essais restants avant verrouillage (informatif)."""
    return max(0, MAX_TENTATIVES - echecs_consecutifs(identifiant))


def lister_echecs(limite: int = 200) -> list[dict[str, Any]]:
    """Journal des tentatives echouees, les plus recentes en premier."""
    conn = _connexion()
    try:
        curseur = conn.execute(
            "SELECT id, identifiant, horodatage, echecs_consecutifs, verrouillage_declenche "
            "FROM echecs ORDER BY id DESC LIMIT ?",
            (limite,),
        )
        colonnes = [d[0] for d in curseur.description]
        return [dict(zip(colonnes, ligne)) for ligne in curseur.fetchall()]
    finally:
        conn.close()


def formater_duree(secondes: int) -> str:
    """Formate un temps restant pour affichage ('4 min 12 s', '45 s')."""
    if secondes <= 0:
        return "0 s"
    minutes, sec = divmod(int(secondes), 60)
    if minutes and sec:
        return f"{minutes} min {sec} s"
    if minutes:
        return f"{minutes} min"
    return f"{sec} s"
