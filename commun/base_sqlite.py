"""
Ouverture standardisee des bases SQLite de l'application.

Pourquoi ce module
------------------
Trois modules ouvrent une base SQLite : audit/journal.py (journal d'audit),
auth/tentatives.py (tentatives de connexion) et gouvernance/workflow_seuils.py
(propositions de changement de regles). Chacun repetait le meme bloc de
configuration (PRAGMA, timeout, gestion des transactions).

Cette duplication a produit exactement le defaut qu'on lui connait : les copies
ont diverge. Le module de gouvernance etait reste en `journal_mode=MEMORY`,
sans timeout ni pilotage explicite des transactions, alors que les deux autres
avaient ete durcis -- ses propositions en attente n'etaient donc pas durables,
et il echouait sur "database is locked" des que deux sessions ecrivaient en
meme temps.

Une seule definition, une seule regle a faire evoluer.

Configuration retenue et compromis
----------------------------------
journal_mode=DELETE
    Journal de rollback sur disque. Une transaction interrompue est annulee
    proprement, jamais laissee a demi-ecrite. `MEMORY` (l'ancien choix) garde
    ce journal en RAM : un crash pendant une ecriture peut CORROMPRE la base.
    Pour des donnees dont l'interet est d'etre opposables (audit, gouvernance),
    c'est le mauvais compromis.

synchronous=FULL
    fsync a chaque commit : une ecriture confirmee est reellement sur le
    disque, meme en cas de coupure de courant.

    Cout assume : ~25 ms par commit. Sans consequence tant qu'on ne commit
    qu'une fois par action utilisateur -- d'ou l'importance d'ecrire les lots
    en UNE transaction (voir audit.journal._ajouter_entrees) plutot qu'une
    transaction par ligne.

WAL : ecarte volontairement
    Plus rapide et meilleur en lecture concurrente, mais il s'appuie sur de la
    memoire partagee (fichiers -wal / -shm) qui echoue precisement sur les
    partages reseau et dossiers synchronises vises au depart. DELETE est le
    mode a la fois portable ET durable.

timeout=30 s
    Si une autre connexion detient le verrou d'ecriture, on attend au lieu
    d'echouer immediatement sur "database is locked".

isolation_level=None
    Desactive la gestion implicite des transactions par le module sqlite3, qui
    n'emet un BEGIN qu'au premier INSERT -- donc APRES une eventuelle lecture
    preparatoire. Les appelants qui doivent rendre un cycle
    lire-puis-ecrire indivisible emettent eux-memes `BEGIN IMMEDIATE`, qui
    prend le verrou d'ecriture des le debut. C'est ce qui empeche deux
    ecrivains concurrents de lire le meme etat avant d'ecrire (fourche de la
    chaine d'audit, compteur d'echecs fausse).
"""
from __future__ import annotations

import sqlite3

# Duree d'attente du verrou d'ecriture avant abandon.
TIMEOUT_VERROU_SECONDES = 30.0


def connexion_durable(chemin: str) -> sqlite3.Connection:
    """Ouvre une connexion SQLite configuree pour la durabilite.

    L'appelant reste responsable de creer ses tables et de piloter ses
    transactions (`BEGIN IMMEDIATE` s'il enchaine une lecture et une ecriture
    qui doivent etre indivisibles).
    """
    conn = sqlite3.connect(chemin, timeout=TIMEOUT_VERROU_SECONDES, isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("PRAGMA synchronous=FULL")
    except sqlite3.DatabaseError:  # pragma: no cover - environnement degrade
        # Repli : mieux vaut une base fonctionnelle en mode degrade qu'une
        # application qui refuse de demarrer. Pour le journal d'audit, l'ancre
        # externe continue de detecter toute alteration.
        conn.execute("PRAGMA journal_mode=MEMORY")
    return conn
