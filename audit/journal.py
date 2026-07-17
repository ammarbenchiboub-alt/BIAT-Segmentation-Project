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
    - Ancre d'integrite EXTERNE (audit/ancre.json, hors de journal.sqlite3) :
      le chainage seul ne detecte PAS la suppression des DERNIERES entrees.
      En effet, supprimer les N derniers enregistrements laisse une chaine
      qui reste parfaitement valide depuis la genese : rien, dans le fichier
      .sqlite3, ne dit combien d'entrees devraient exister. L'ancre corrige
      ce angle mort en conservant, a l'exterieur de la base, le nombre
      d'entrees attendu et le hash de la derniere entree. verifier_integrite()
      confronte systematiquement le journal a cette ancre.

Matrice de detection (voir verifier_integrite) :

    | Attaque                        | Detectee par                      |
    |--------------------------------|-----------------------------------|
    | Modification d'une entree      | recalcul du hash de l'entree      |
    | Reorganisation des entrees     | chainage hash_precedent           |
    | Suppression au milieu          | chainage hash_precedent           |
    | Suppression des dernieres      | ancre externe (nombre + hash)     |
    | Ajout d'entrees non tracees    | ancre externe (nombre + hash)     |
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
import threading
from datetime import datetime, timezone
from typing import Any

from commun import connexion_durable

# Champs du profil client conserves dans le journal. Definis une seule fois :
# la liste servait auparavant en dur dans enregistrer_lot, ou elle risquait de
# diverger du 8e champ ajoute au moteur.
_CHAMPS_PROFIL = (
    "Marche", "Profession", "Age", "MMM", "VRD", "Nationalite", "Residence",
    "EpargnantDeposantExclusif",
)

# Serialise les ecritures entre les threads du processus Streamlit (une session
# = un thread). Voir _ajouter_entrees pour le detail du risque de fourche.
_VERROU_ECRITURE = threading.Lock()

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHEMIN_JOURNAL = os.path.join(_BASE_DIR, "journal.sqlite3")
# Ancre d'integrite : volontairement HORS de journal.sqlite3, pour qu'une
# alteration du journal ne puisse pas ajuster en meme temps le temoin qui
# permet de la detecter.
CHEMIN_ANCRE = os.path.join(_BASE_DIR, "ancre.json")

_GENESE = "GENESE"


def _connexion() -> sqlite3.Connection:
    # Configuration de durabilite centralisee dans commun/base_sqlite.py
    # (journal_mode=DELETE + synchronous=FULL, timeout, transactions
    # explicites). Voir ce module pour le detail des compromis.
    conn = connexion_durable(CHEMIN_JOURNAL)
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
    decision donnee, meme si les seuils sont modifies plus tard.

    Delegue a core.rules_loader.empreinte_regles : meme empreinte que celle
    qui sert de clef de cache au moteur, donc une seule definition de "version
    des regles" dans toute l'application."""
    from core.rules_loader import empreinte_regles

    return empreinte_regles()


# --------------------------------------------------------------------------- #
# Ancre d'integrite externe (detection du tronquage de fin)
# --------------------------------------------------------------------------- #
def _lire_ancre() -> dict[str, Any] | None:
    """Lit l'ancre. Renvoie None si elle n'existe pas encore."""
    if not os.path.exists(CHEMIN_ANCRE):
        return None
    try:
        with open(CHEMIN_ANCRE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        # Ancre illisible = ancre corrompue : traitee comme une anomalie par
        # verifier_integrite, jamais ignoree silencieusement.
        return {"_illisible": True}


def _ecrire_ancre(nombre_entrees: int, dernier_hash: str) -> None:
    """Ecrit l'ancre de facon atomique (fichier temporaire puis os.replace).

    L'atomicite evite qu'une coupure pendant l'ecriture laisse une ancre
    tronquee, qui ferait echouer a tort tous les controles ulterieurs."""
    contenu = {
        "nombre_entrees": nombre_entrees,
        "dernier_hash": dernier_hash,
        "horodatage": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "_avertissement": (
            "Temoin d'integrite du journal d'audit. Ne pas modifier ni supprimer : "
            "toute divergence avec audit/journal.sqlite3 est signalee comme une "
            "alteration lors du controle d'integrite."
        ),
    }
    # Nom de fichier temporaire UNIQUE par processus et par thread. Un nom
    # partage (ancre.json.tmp) faisait echouer les ecritures concurrentes sous
    # Windows : deux threads ouvraient le meme fichier, et os.replace levait
    # PermissionError ("fichier utilise par un autre processus"). Streamlit
    # servant chaque session dans un thread du meme processus, le cas est
    # courant des que deux conseillers utilisent l'application en meme temps.
    temporaire = f"{CHEMIN_ANCRE}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(temporaire, "w", encoding="utf-8") as f:
            json.dump(contenu, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporaire, CHEMIN_ANCRE)
    finally:
        # Ne jamais laisser de .tmp orphelin derriere une erreur.
        if os.path.exists(temporaire):
            try:
                os.remove(temporaire)
            except OSError:  # pragma: no cover
                pass


def assurer_ancre() -> dict[str, Any]:
    """Cree l'ancre a partir de l'etat courant du journal si elle n'existe pas.

    Necessaire pour CONSERVER L'HISTORIQUE EXISTANT : le journal a ete cree
    avant l'introduction de l'ancre, on ne peut donc pas exiger qu'elle ait
    toujours ete la. On l'initialise sur l'etat actuel.

    Limite explicite et assumee : les entrees anterieures a la creation de
    l'ancre ne sont couvertes contre le tronquage de fin qu'A PARTIR de cette
    initialisation (une suppression qui aurait eu lieu AVANT est indetectable,
    puisqu'aucun temoin n'existait). Le chainage de hash, lui, couvre bien
    l'integralite de l'historique depuis la genese. Renvoie l'ancre en place."""
    ancre = _lire_ancre()
    if ancre is not None and not ancre.get("_illisible"):
        return ancre
    conn = _connexion()
    try:
        nombre = conn.execute("SELECT COUNT(*) FROM journal").fetchone()[0]
        dernier = _derniere_entree(conn)
    finally:
        conn.close()
    _ecrire_ancre(nombre, dernier)
    return _lire_ancre()


def _derniere_entree(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT hash_entree FROM journal ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else _GENESE


def _calculer_hash(champs: dict, hash_precedent: str) -> str:
    contenu = json.dumps(champs, sort_keys=True, ensure_ascii=False) + hash_precedent
    return hashlib.sha256(contenu.encode("utf-8")).hexdigest()


def _ajouter_entrees(
    type_action: str,
    utilisateur: dict[str, Any],
    decisions: list[tuple[dict[str, Any], str | None, str | None, str | None]],
) -> int:
    """Ajoute N decisions au journal, en UNE SEULE transaction serialisee.

    Point d'ecriture UNIQUE du module : enregistrer() et enregistrer_lot() sont
    tous deux de simples adaptateurs au-dessus de cette fonction. Il n'existe
    donc qu'une seule implementation du chainage de hash et de la mise a jour
    de l'ancre -- une regle a maintenir, pas deux.

    Concurrence
    -----------
    Streamlit sert chaque session dans un THREAD du meme processus : deux
    conseillers qui segmentent au meme instant executent reellement ce code en
    parallele. Sans protection, deux ecritures simultanees lisent le meme
    `hash_precedent` et produisent une FOURCHE dans la chaine : deux entrees
    referencant le meme parent, ce que verifier_integrite signalerait ensuite,
    a tort, comme une alteration -- et de facon irreversible.

    Double protection, chacune couvrant un cas que l'autre ne couvre pas :
      - _VERROU_ECRITURE (threading.Lock) : serialise les threads du processus
        Streamlit. C'est le cas reel et frequent.
      - BEGIN IMMEDIATE : prend le verrou d'ecriture SQLite des le debut de la
        transaction, ce qui serialise aussi des PROCESSUS distincts (deux
        instances de l'application, un script de maintenance...). Sans lui,
        SQLite n'acquiert le verrou qu'au premier INSERT, donc APRES la lecture
        du hash precedent : la fourche resterait possible.

    Performance
    -----------
    Le lot entier tient dans une transaction, une connexion, une lecture du
    fichier de regles et une ecriture d'ancre. La version precedente refaisait
    tout cela POUR CHAQUE LIGNE : un import de 300 lignes prenait 8,3 s
    (27,7 ms/ligne, soit ~138 s pour 5 000 lignes) a cause d'un fsync et d'une
    relecture du JSON de regles par ligne.

    Renvoie le nombre d'entrees ajoutees.
    """
    if not decisions:
        return 0

    horodatage = datetime.now(timezone.utc).isoformat(timespec="seconds")
    # Lu UNE seule fois pour tout le lot : toutes les decisions d'un meme lot
    # sont, par construction, prises avec la meme version des regles.
    version_regles = _hash_regles_actives()

    with _VERROU_ECRITURE:
        conn = _connexion()
        try:
            # Verrou d'ecriture pris AVANT la lecture du dernier hash.
            conn.execute("BEGIN IMMEDIATE")
            hash_courant = _derniere_entree(conn)
            for profil, segment, sous_segment, regle_id in decisions:
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
                hash_entree = _calculer_hash(champs, hash_courant)
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
                    {**champs, "hash_precedent": hash_courant, "hash_entree": hash_entree},
                )
                hash_courant = hash_entree
            nombre_entrees = conn.execute("SELECT COUNT(*) FROM journal").fetchone()[0]
            conn.commit()
        except Exception:
            # Tout ou rien : un lot partiellement ecrit laisserait une chaine
            # coherente mais une ancre fausse.
            conn.rollback()
            raise
        finally:
            conn.close()

        # Ancre mise a jour APRES le commit, mais TOUJOURS sous _VERROU_ECRITURE :
        # deux ecrivains ne peuvent donc pas publier une ancre dans le desordre.
        # Si l'application est interrompue entre le commit et cette ligne, le
        # journal contient plus d'entrees que l'ancre : verifier_integrite le
        # signale distinctement d'un tronquage (journal en avance = ecriture
        # interrompue ; journal en retard = entrees supprimees). Aucune entree
        # n'est jamais perdue.
        _ecrire_ancre(nombre_entrees, hash_courant)

    return len(decisions)


def enregistrer(
    type_action: str,
    utilisateur: dict[str, Any],
    profil: dict[str, Any],
    segment: str | None,
    sous_segment: str | None,
    regle_id: str | None,
) -> None:
    """Ajoute une entree au journal. Ne modifie et ne supprime jamais une
    entree existante (append-only). API inchangee."""
    _ajouter_entrees(type_action, utilisateur, [(profil, segment, sous_segment, regle_id)])


def enregistrer_lot(
    type_action: str,
    utilisateur: dict[str, Any],
    lignes: list[dict[str, Any]],
) -> int:
    """Enregistre plusieurs decisions d'un coup (import de masse). Chaque
    ligne du lot devient sa propre entree chainee dans le journal, pour
    garder une tracabilite ligne par ligne identique a la simulation
    individuelle. Renvoie le nombre d'entrees ajoutees.

    API inchangee. En interne, le lot est desormais ecrit en UNE transaction
    (voir _ajouter_entrees) au lieu d'un appel a enregistrer() par ligne."""
    decisions = [
        (
            {k: v for k, v in ligne.items() if k in _CHAMPS_PROFIL},
            ligne.get("Segment"),
            ligne.get("Sous_segment"),
            ligne.get("Regle") or ligne.get("Regle_ID"),
        )
        for ligne in lignes
    ]
    return _ajouter_entrees(type_action, utilisateur, decisions)


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
    """Controle complet de l'integrite du journal. Renvoie (True, message) si
    tout est intact, (False, message) decrivant l'anomalie sinon.

    Deux controles complementaires, tous deux necessaires :

    1. CHAINAGE (interne au journal) : chaque entree est rehachee et comparee
       a son hash stocke, et le chainage hash_precedent est reverifie depuis
       la genese. Detecte toute modification, reorganisation ou suppression
       AU MILIEU de l'historique.

    2. ANCRE EXTERNE (audit/ancre.json) : le nombre d'entrees et le hash de la
       derniere entree sont compares au temoin conserve hors de la base.
       Detecte la suppression des DERNIERES entrees (tail truncation), que le
       chainage seul ne peut pas voir : un journal tronque par la fin reste
       une chaine valide depuis la genese.
    """
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

    # --- Controle 2 : confrontation a l'ancre externe ----------------------
    ancre = _lire_ancre()
    if ancre is None:
        # Aucun temoin : on ne peut rien affirmer sur le tronquage de fin.
        # On le dit explicitement plutot que d'annoncer un journal "intact".
        assurer_ancre()
        return True, (
            f"Chaine intacte : {len(lignes)} entree(s) verifiee(s). "
            "Ancre d'integrite absente : elle vient d'etre initialisee sur l'etat "
            "actuel. La detection de suppression des dernieres entrees sera active "
            "a partir de maintenant."
        )
    if ancre.get("_illisible"):
        return False, (
            "Ancre d'integrite (audit/ancre.json) illisible ou corrompue : "
            "impossible de garantir qu'aucune entree recente n'a ete supprimee."
        )

    attendu_nombre = ancre.get("nombre_entrees")
    attendu_hash = ancre.get("dernier_hash")
    if not isinstance(attendu_nombre, int) or not isinstance(attendu_hash, str):
        return False, (
            "Ancre d'integrite (audit/ancre.json) incomplete : champs 'nombre_entrees' "
            "ou 'dernier_hash' absents ou invalides. Impossible de garantir qu'aucune "
            "entree recente n'a ete supprimee."
        )
    reel_nombre = len(lignes)
    reel_hash = lignes[-1][12] if lignes else _GENESE

    if reel_nombre < attendu_nombre:
        manquantes = attendu_nombre - reel_nombre
        return False, (
            f"ALTERATION DETECTEE : {manquantes} entree(s) manquante(s) en fin de journal "
            f"({reel_nombre} presentes, {attendu_nombre} attendues d'apres l'ancre). "
            "Suppression des enregistrements les plus recents."
        )
    if reel_nombre > attendu_nombre:
        surplus = reel_nombre - attendu_nombre
        if surplus == 1:
            return False, (
                "Incoherence : le journal contient 1 entree de plus que l'ancre. "
                "Probable ecriture interrompue (arret entre l'ajout et la mise a jour "
                "de l'ancre), ou entree ajoutee hors de l'application."
            )
        return False, (
            f"ALTERATION DETECTEE : {surplus} entree(s) ajoutee(s) sans passer par "
            f"l'application ({reel_nombre} presentes, {attendu_nombre} attendues)."
        )
    if reel_hash != attendu_hash:
        return False, (
            "ALTERATION DETECTEE : la derniere entree ne correspond pas a l'ancre "
            "(nombre d'entrees correct mais hash de fin different). Des entrees ont "
            "probablement ete supprimees puis remplacees."
        )

    return True, (
        f"Journal intact : {len(lignes)} entree(s) verifiee(s), chaine ininterrompue "
        "et conforme a l'ancre d'integrite externe (aucune suppression en fin de journal)."
    )
