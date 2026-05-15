"""
╔══════════════════════════════════════════════════════════════════════╗
║   CONNEXION MySQL — SIMULATEUR BIAT  v4.0                           ║
║   ✅ PART et PRO séparés                                            ║
║   ✅ Professions depuis table MySQL                                 ║
║   ✅ Dormants calculés automatiquement via nb_operations            ║
║   ✅ Stockage complet des simulations avec JSON des paramètres      ║
║   ✅ Export PDF + Dashboard                                         ║
╚══════════════════════════════════════════════════════════════════════╝

Installation :
    pip install mysql-connector-python pandas

Utilisation :
    from db_biat import BiatDB
    db = BiatDB()
    db.sauvegarder_simulation(client, resultat, parametres)
"""

import mysql.connector
from mysql.connector import Error
import pandas as pd
import json
from datetime import datetime
from typing import Optional, List, Dict

# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────
CONFIG_DB = {
    "host":     "localhost",
    "port":     3306,
    "user":     "root",
    "password": "TON_MOT_DE_PASSE",   # ← Modifier ici
    "database": "db_simulateur_biat",
    "charset":  "utf8mb4",
    "autocommit": False,
}

# Mapping marché → id (correspond aux INSERT du SQL)
MARCHE_IDS = {
    "Particulier":  1,  # PART
    "Professionnel":2,  # PRO
    "TRE":          3,
    "ENR":          4,
}


# ─────────────────────────────────────────────────────────────────────
class BiatDB:
    """Gestionnaire BDD du simulateur BIAT."""

    def __init__(self):
        self.config     = CONFIG_DB
        self.connexion  = None
        self._professions_cache = None

    # ── Connexion ─────────────────────────────────────────────────
    def connecter(self) -> bool:
        try:
            self.connexion = mysql.connector.connect(**self.config)
            if self.connexion.is_connected():
                print("✅ Connexion MySQL établie")
                return True
        except Error as e:
            print(f"❌ Erreur connexion : {e}")
            return False

    def deconnecter(self):
        if self.connexion and self.connexion.is_connected():
            self.connexion.close()
            print("🔌 Connexion fermée")

    def _exec(self, sql: str, params=None, fetch=False, many=False):
        """Exécute une requête SQL."""
        try:
            if not self.connexion or not self.connexion.is_connected():
                self.connecter()
            cur = self.connexion.cursor(dictionary=True)
            if many:
                cur.executemany(sql, params or [])
            else:
                cur.execute(sql, params or ())
            if fetch:
                return cur.fetchall()
            self.connexion.commit()
            return cur.lastrowid
        except Error as e:
            print(f"❌ Erreur SQL : {e}")
            if self.connexion:
                self.connexion.rollback()
            return None

    # ── PROFESSIONS ────────────────────────────────────────────────
    def get_professions(self, categorie: str = None) -> List[Dict]:
        """Récupère les professions depuis MySQL."""
        if self._professions_cache is None:
            self._professions_cache = self._exec(
                "SELECT * FROM PROFESSION ORDER BY libelle", fetch=True
            ) or []
        if categorie:
            return [p for p in self._professions_cache if p["categorie"] == categorie]
        return self._professions_cache

    def get_professions_libelle(self) -> List[str]:
        """Retourne la liste des libellés pour Streamlit."""
        profs = self.get_professions()
        return sorted([p["libelle"] for p in profs]) if profs else []

    def get_professions_potentiel(self) -> List[str]:
        """Professions à potentiel HG (Annexe 4)."""
        profs = self.get_professions()
        return [p["libelle"] for p in profs if p.get("est_potentiel")]

    def get_professions_liberales(self) -> List[str]:
        """Professions libérales (Annexe 5)."""
        profs = self.get_professions()
        return [p["libelle"] for p in profs if p.get("est_liberal")]

    def get_id_profession(self, libelle: str) -> Optional[int]:
        """Retourne l'id d'une profession par son libellé."""
        profs = self.get_professions()
        for p in profs:
            if p["libelle"] == libelle:
                return p["id_profession"]
        return None

    # ── MARCHÉS ────────────────────────────────────────────────────
    def get_marche_id(self, forme_juridique: str, marche_input: str) -> int:
        """
        Retourne l'id du marché selon la forme juridique et le marché saisi.
        PART et PRO sont maintenant séparés.
        """
        if marche_input == "TRE":
            return 3
        elif marche_input == "ENR":
            return 4
        elif forme_juridique == "Professionnel":
            return 2  # PRO
        else:
            return 1  # PART

    # ── CLIENTS ────────────────────────────────────────────────────
    def ajouter_ou_maj_client(self, client: dict) -> Optional[int]:
        """
        Insère ou met à jour un client.
        Retourne l'id_client.
        """
        marche_input  = client.get("marche_input", "PART & PRO")
        forme_jur     = client.get("forme_juridique", "Particulier")
        id_marche     = self.get_marche_id(forme_jur, marche_input)
        id_profession = self.get_id_profession(client.get("profession", ""))
        code_client   = client.get(
            "code_client",
            f"CLI_{datetime.now().strftime('%Y%m%d%H%M%S%f')[:16]}"
        )

        sql = """
            INSERT INTO CLIENT
                (code_client, age, forme_juridique, id_profession,
                 qualite_residence, nationalite, id_marche)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                age              = VALUES(age),
                forme_juridique  = VALUES(forme_juridique),
                id_profession    = VALUES(id_profession),
                qualite_residence= VALUES(qualite_residence),
                nationalite      = VALUES(nationalite),
                id_marche        = VALUES(id_marche)
        """
        id_client = self._exec(sql, (
            code_client,
            client.get("age", 1),
            forme_jur,
            id_profession,
            client.get("residence", "Résident"),
            client.get("nationalite", "Tunisienne"),
            id_marche
        ))

        # Récupérer l'id si ON DUPLICATE KEY
        if not id_client:
            res = self._exec(
                "SELECT id_client FROM CLIENT WHERE code_client = %s",
                (code_client,), fetch=True
            )
            if res:
                id_client = res[0]["id_client"]

        # Données financières
        if id_client:
            nb_ops = client.get("nb_operations_12m", 0)
            sql_fin = """
                INSERT INTO DONNEES_FINANCIERES
                    (id_client, mmm, vrd, revenus_declaratifs,
                     total_engagements, nb_operations_12m)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    mmm               = VALUES(mmm),
                    vrd               = VALUES(vrd),
                    revenus_declaratifs=VALUES(revenus_declaratifs),
                    total_engagements = VALUES(total_engagements),
                    nb_operations_12m = VALUES(nb_operations_12m)
            """
            self._exec(sql_fin, (
                id_client,
                client.get("mmm", 0.0),
                client.get("vrd", 0.0),
                client.get("revenus_declaratifs", 0.0),
                client.get("total_engagements", 0.0),
                nb_ops
            ))

        return id_client

    def get_client(self, code_client: str) -> Optional[Dict]:
        """Récupère un client complet avec ses données financières."""
        sql = """
            SELECT c.*, p.libelle AS profession_libelle,
                   p.est_potentiel, p.est_liberal,
                   m.libelle AS marche_libelle,
                   df.mmm, df.vrd, df.nb_operations_12m, df.est_actif
            FROM CLIENT c
            LEFT JOIN PROFESSION p ON c.id_profession = p.id_profession
            LEFT JOIN MARCHE m     ON c.id_marche     = m.id_marche
            LEFT JOIN DONNEES_FINANCIERES df ON c.id_client = df.id_client
            WHERE c.code_client = %s
        """
        res = self._exec(sql, (code_client,), fetch=True)
        return res[0] if res else None

    # ── SIMULATIONS ────────────────────────────────────────────────
    def sauvegarder_simulation(
        self,
        client:     dict,
        resultat:   dict,
        parametres: dict = None,
        id_utilisateur: int = None
    ) -> Optional[int]:
        """
        Sauvegarde une simulation complète.

        Parameters:
            client     : données du client
            resultat   : dict retourné par segmenter_client()
            parametres : dict des seuils utilisés (pour traçabilité)
            id_utilisateur : agent BIAT qui lance la simulation

        Returns:
            id_simulation créé
        """
        # 1. Créer/mettre à jour le client
        id_client = self.ajouter_ou_maj_client(client)
        if not id_client:
            print("❌ Impossible de créer le client")
            return None

        # 2. Trouver le sous-segment dans la BDD
        sql_seg = """
            SELECT ss.id_sous_segment
            FROM SOUS_SEGMENT ss
            WHERE ss.libelle_sous_segment = %s
            LIMIT 1
        """
        seg_res = self._exec(sql_seg, (resultat.get("sous_segment", ""),), fetch=True)
        if not seg_res:
            # Fallback : chercher par segment
            sql_seg2 = """
                SELECT id_sous_segment FROM SOUS_SEGMENT
                WHERE libelle_segment = %s LIMIT 1
            """
            seg_res = self._exec(sql_seg2, (resultat.get("segment", ""),), fetch=True)

        if not seg_res:
            print(f"⚠️ Sous-segment '{resultat.get('sous_segment')}' introuvable en BDD")
            return None

        id_sous_segment = seg_res[0]["id_sous_segment"]

        # 3. Justification
        justification = " | ".join(resultat.get("explication", []))

        # 4. Paramètres JSON
        params_json = json.dumps(parametres, ensure_ascii=False) if parametres else None

        # 5. Insérer la simulation
        nb_ops = client.get("nb_operations_12m", 0)
        est_actif = nb_ops > 0  # Calcul automatique

        sql_sim = """
            INSERT INTO SIMULATION (
                id_client, id_sous_segment, id_utilisateur,
                mmm_utilise, vrd_utilise, age_utilise,
                nb_ops_utilise, est_actif_utilise,
                forme_juridique_utilisee,
                justification, parametres_json
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        id_sim = self._exec(sql_sim, (
            id_client,
            id_sous_segment,
            id_utilisateur or 1,
            client.get("mmm", 0.0),
            client.get("vrd", 0.0),
            client.get("age", 1),
            nb_ops,
            est_actif,
            client.get("forme_juridique", "Particulier"),
            justification,
            params_json
        ))

        if id_sim:
            print(f"✅ Simulation #{id_sim} — {resultat['segment']} / {resultat['sous_segment']}")
        return id_sim

    # ── STATISTIQUES ────────────────────────────────────────────────
    def get_distribution_segments(self) -> pd.DataFrame:
        """Distribution des segments (dernière simulation par client)."""
        sql = """
            SELECT
                m.libelle               AS marche,
                ss.libelle_segment      AS segment,
                ss.libelle_sous_segment AS sous_segment,
                ss.badge_couleur,
                COUNT(DISTINCT s.id_client) AS nb_clients,
                ROUND(AVG(s.mmm_utilise),3) AS mmm_moyen,
                ROUND(AVG(s.vrd_utilise),3)  AS vrd_moyen,
                ROUND(AVG(s.age_utilise),1)  AS age_moyen
            FROM SIMULATION s
            JOIN SOUS_SEGMENT ss ON s.id_sous_segment = ss.id_sous_segment
            JOIN MARCHE m        ON ss.id_marche      = m.id_marche
            WHERE s.id_simulation IN (
                SELECT MAX(id_simulation) FROM SIMULATION GROUP BY id_client
            )
            GROUP BY m.libelle, ss.libelle_segment, ss.libelle_sous_segment, ss.badge_couleur
            ORDER BY nb_clients DESC
        """
        res = self._exec(sql, fetch=True)
        return pd.DataFrame(res) if res else pd.DataFrame()

    def get_clients_dormants(self) -> pd.DataFrame:
        """Retourne les clients dormants (nb_operations = 0)."""
        sql = """
            SELECT c.code_client, c.age, c.forme_juridique,
                   p.libelle AS profession,
                   m.libelle AS marche,
                   df.mmm, df.vrd, df.nb_operations_12m
            FROM CLIENT c
            JOIN DONNEES_FINANCIERES df ON c.id_client    = df.id_client
            JOIN MARCHE m               ON c.id_marche    = m.id_marche
            LEFT JOIN PROFESSION p      ON c.id_profession= p.id_profession
            WHERE df.nb_operations_12m = 0
            ORDER BY df.vrd DESC
        """
        res = self._exec(sql, fetch=True)
        return pd.DataFrame(res) if res else pd.DataFrame()

    def get_historique_client(self, code_client: str) -> pd.DataFrame:
        """Historique des simulations d'un client."""
        sql = """
            SELECT s.date_simulation,
                   ss.libelle_segment, ss.libelle_sous_segment,
                   s.mmm_utilise, s.vrd_utilise, s.age_utilise,
                   s.nb_ops_utilise, s.est_actif_utilise,
                   s.justification
            FROM SIMULATION s
            JOIN CLIENT c        ON s.id_client       = c.id_client
            JOIN SOUS_SEGMENT ss ON s.id_sous_segment = ss.id_sous_segment
            WHERE c.code_client = %s
            ORDER BY s.date_simulation DESC
        """
        res = self._exec(sql, (code_client,), fetch=True)
        return pd.DataFrame(res) if res else pd.DataFrame()

    def get_stats_globales(self) -> dict:
        """Retourne les KPIs globaux."""
        queries = {
            "total_simulations": "SELECT COUNT(*) AS n FROM SIMULATION",
            "total_clients":     "SELECT COUNT(*) AS n FROM CLIENT",
            "clients_dormants":  "SELECT COUNT(*) AS n FROM DONNEES_FINANCIERES WHERE nb_operations_12m = 0",
            "part_clients":      "SELECT COUNT(*) AS n FROM CLIENT WHERE forme_juridique = 'Particulier'",
            "pro_clients":       "SELECT COUNT(*) AS n FROM CLIENT WHERE forme_juridique = 'Professionnel'",
        }
        stats = {}
        for key, sql in queries.items():
            res = self._exec(sql, fetch=True)
            stats[key] = res[0]["n"] if res else 0
        return stats

    def get_analyse_sensibilite(self, variable: str, valeurs: list) -> pd.DataFrame:
        """
        Analyse de sensibilité : combien de clients changeraient de segment
        si on modifiait le seuil d'une variable.
        """
        sql = f"""
            SELECT
                ROUND({variable}_utilise, 0) AS valeur,
                ss.libelle_sous_segment,
                COUNT(*) AS nb_clients
            FROM SIMULATION s
            JOIN SOUS_SEGMENT ss ON s.id_sous_segment = ss.id_sous_segment
            WHERE s.id_simulation IN (
                SELECT MAX(id_simulation) FROM SIMULATION GROUP BY id_client
            )
            GROUP BY ROUND({variable}_utilise, 0), ss.libelle_sous_segment
            ORDER BY valeur ASC
        """
        res = self._exec(sql, fetch=True)
        return pd.DataFrame(res) if res else pd.DataFrame()

    def sauvegarder_masse(self, df_resultats: pd.DataFrame) -> int:
        """
        Sauvegarde en masse les résultats d'une simulation CSV.
        Retourne le nombre de simulations sauvegardées.
        """
        count = 0
        for _, row in df_resultats.iterrows():
            client  = row.to_dict()
            resultat = {
                "segment":     client.get("segment",     ""),
                "sous_segment":client.get("sous_segment",""),
                "explication": ["Import en masse depuis CSV"]
            }
            if self.sauvegarder_simulation(client, resultat):
                count += 1
        print(f"✅ {count}/{len(df_resultats)} simulations sauvegardées")
        return count


# ─────────────────────────────────────────────────────────────────────
# TEST RAPIDE
# ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    db = BiatDB()
    if db.connecter():

        # Test professions depuis MySQL
        profs = db.get_professions()
        print(f"\n📋 {len(profs)} professions chargées depuis MySQL")
        print(f"   Professions à potentiel : {db.get_professions_potentiel()[:3]}...")

        # Test simulation
        client_test = {
            "code_client":       "TEST_PART_001",
            "marche_input":      "PART & PRO",
            "forme_juridique":   "Particulier",
            "age":               45,
            "mmm":               5.5,
            "vrd":               150.0,
            "profession":        "Ingénieur",
            "residence":         "Résident",
            "nationalite":       "Tunisienne",
            "nb_operations_12m": 36,  # → est_actif = True automatiquement
        }
        resultat_test = {
            "segment":     "Haut de Gamme",
            "sous_segment":"Affluent",
            "explication": ["Particulier · âge 45 ≥ 30 · VRD 150 mD ∈ [100,300[ → Affluent"]
        }
        db.sauvegarder_simulation(client_test, resultat_test)

        # Test client dormant
        client_dormant = {
            "code_client":       "TEST_DORMANT_001",
            "marche_input":      "PART & PRO",
            "forme_juridique":   "Particulier",
            "age":               55,
            "mmm":               0.0,
            "vrd":               2.0,
            "profession":        "Retraité",
            "residence":         "Résident",
            "nationalite":       "Tunisienne",
            "nb_operations_12m": 0,  # → est_actif = False automatiquement → Dormant
        }
        resultat_dormant = {
            "segment":     "Grand Public",
            "sous_segment":"Clients dormants",
            "explication": ["nb_operations_12m = 0 → Client dormant (calcul automatique)"]
        }
        db.sauvegarder_simulation(client_dormant, resultat_dormant)

        # Stats
        stats = db.get_stats_globales()
        print(f"\n📊 Stats globales : {stats}")
        print(f"\n🛌 Clients dormants :\n{db.get_clients_dormants()}")
        print(f"\n📈 Distribution :\n{db.get_distribution_segments()}")

        db.deconnecter()
