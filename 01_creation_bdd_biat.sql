-- ╔══════════════════════════════════════════════════════════════════╗
-- ║   SCRIPT SQL — BASE DE DONNÉES SIMULATEUR BIAT  v4.0           ║
-- ║   MySQL 8.0+                                                    ║
-- ║   Corrections :                                                 ║
-- ║   ✅ PART séparé de PRO                                        ║
-- ║   ✅ Table PROFESSION dédiée                                   ║
-- ║   ✅ Calcul automatique dormants via nb_operations              ║
-- ║   ✅ Stockage complet des simulations                          ║
-- ║   ✅ Toutes les données de référence BIAT (Note 2023-06)       ║
-- ╚══════════════════════════════════════════════════════════════════╝

CREATE DATABASE IF NOT EXISTS db_simulateur_biat
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE db_simulateur_biat;

-- ─────────────────────────────────────────────────────────────────
-- DÉSACTIVER LES CONTRAINTES TEMPORAIREMENT
-- ─────────────────────────────────────────────────────────────────
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS SIMULATION;
DROP TABLE IF EXISTS DONNEES_FINANCIERES;
DROP TABLE IF EXISTS CLIENT;
DROP TABLE IF EXISTS SOUS_SEGMENT;
DROP TABLE IF EXISTS MARCHE;
DROP TABLE IF EXISTS PROFESSION;
DROP TABLE IF EXISTS UTILISATEUR;
SET FOREIGN_KEY_CHECKS = 1;

-- ─────────────────────────────────────────────────────────────────
-- 1. TABLE MARCHE
--    PART et PRO sont maintenant SÉPARÉS
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE MARCHE (
    id_marche    INT          NOT NULL AUTO_INCREMENT,
    code_marche  VARCHAR(20)  NOT NULL UNIQUE,
    libelle      VARCHAR(80)  NOT NULL,
    description  TEXT,
    date_creation DATETIME    DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_marche)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─────────────────────────────────────────────────────────────────
-- 2. TABLE PROFESSION (Annexes 4 & 5 de la Note BIAT)
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE PROFESSION (
    id_profession   INT          NOT NULL AUTO_INCREMENT,
    libelle         VARCHAR(100) NOT NULL,
    categorie       VARCHAR(50)  NOT NULL, -- HG / LIBERALE_STRAT / LIBERALE_AUTRE / SALARIE_POTENTIEL / AUTRE
    est_potentiel   BOOLEAN      DEFAULT FALSE, -- Annexe 4 : profession à potentiel HG
    est_liberal     BOOLEAN      DEFAULT FALSE, -- Annexe 5 : profession libérale
    PRIMARY KEY (id_profession)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─────────────────────────────────────────────────────────────────
-- 3. TABLE SOUS_SEGMENT
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE SOUS_SEGMENT (
    id_sous_segment      INT          NOT NULL AUTO_INCREMENT,
    id_marche            INT          NOT NULL,
    libelle_segment      VARCHAR(60)  NOT NULL,
    libelle_sous_segment VARCHAR(100) NOT NULL,
    criteres             TEXT,
    badge_couleur        VARCHAR(20)  DEFAULT '#003087',
    ordre_affichage      INT          DEFAULT 0,
    PRIMARY KEY (id_sous_segment),
    FOREIGN KEY (id_marche) REFERENCES MARCHE(id_marche)
        ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─────────────────────────────────────────────────────────────────
-- 4. TABLE CLIENT
--    forme_juridique = 'Particulier' OU 'Professionnel' (séparés)
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE CLIENT (
    id_client         INT          NOT NULL AUTO_INCREMENT,
    code_client       VARCHAR(30)  NOT NULL UNIQUE,
    nom_prenom        VARCHAR(100) DEFAULT NULL,
    age               INT          NOT NULL CHECK (age BETWEEN 1 AND 120),
    forme_juridique   ENUM('Particulier','Professionnel') NOT NULL,
    id_profession     INT          DEFAULT NULL,
    qualite_residence ENUM('Résident','Non Résident')     NOT NULL DEFAULT 'Résident',
    nationalite       VARCHAR(40)  DEFAULT 'Tunisienne',
    id_marche         INT          NOT NULL,
    agence            VARCHAR(60)  DEFAULT NULL,
    date_creation     DATETIME     DEFAULT CURRENT_TIMESTAMP,
    date_maj          DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id_client),
    FOREIGN KEY (id_marche)    REFERENCES MARCHE(id_marche)    ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (id_profession) REFERENCES PROFESSION(id_profession) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─────────────────────────────────────────────────────────────────
-- 5. TABLE DONNEES_FINANCIERES
--    est_actif calculé automatiquement via nb_operations_12m
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE DONNEES_FINANCIERES (
    id_donnees          INT            NOT NULL AUTO_INCREMENT,
    id_client           INT            NOT NULL UNIQUE,
    mmm                 DECIMAL(15,3)  NOT NULL DEFAULT 0.000 COMMENT 'Mouvements Mensuels Moyens (mD)',
    vrd                 DECIMAL(15,3)  NOT NULL DEFAULT 0.000 COMMENT 'Total Avoirs Stables (mD)',
    revenus_declaratifs DECIMAL(15,3)  DEFAULT 0.000,
    total_engagements   DECIMAL(15,3)  DEFAULT 0.000,
    nb_operations_12m   INT            NOT NULL DEFAULT 0 COMMENT 'Nb opérations 12 derniers mois',
    -- est_actif calculé automatiquement : 0 opération = dormant
    est_actif           BOOLEAN        GENERATED ALWAYS AS (nb_operations_12m > 0) VIRTUAL,
    date_maj            DATETIME       DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id_donnees),
    FOREIGN KEY (id_client) REFERENCES CLIENT(id_client) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─────────────────────────────────────────────────────────────────
-- 6. TABLE UTILISATEUR (agents BIAT qui utilisent le simulateur)
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE UTILISATEUR (
    id_utilisateur INT          NOT NULL AUTO_INCREMENT,
    nom_prenom     VARCHAR(100) NOT NULL,
    email          VARCHAR(100) DEFAULT NULL,
    role           ENUM('Analyste','Chargé de clientèle','Manager','Admin') DEFAULT 'Analyste',
    agence         VARCHAR(60)  DEFAULT NULL,
    date_creation  DATETIME     DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id_utilisateur)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─────────────────────────────────────────────────────────────────
-- 7. TABLE SIMULATION (cœur du simulateur)
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE SIMULATION (
    id_simulation    INT            NOT NULL AUTO_INCREMENT,
    id_client        INT            NOT NULL,
    id_sous_segment  INT            NOT NULL,
    id_utilisateur   INT            DEFAULT NULL,
    date_simulation  DATETIME       DEFAULT CURRENT_TIMESTAMP,
    -- Valeurs au moment de la simulation (snapshot)
    mmm_utilise      DECIMAL(15,3)  NOT NULL DEFAULT 0.000,
    vrd_utilise      DECIMAL(15,3)  NOT NULL DEFAULT 0.000,
    age_utilise      INT            NOT NULL DEFAULT 0,
    nb_ops_utilise   INT            NOT NULL DEFAULT 0,
    est_actif_utilise BOOLEAN       NOT NULL DEFAULT TRUE,
    forme_juridique_utilisee ENUM('Particulier','Professionnel') NOT NULL,
    justification    TEXT           COMMENT 'Règles appliquées expliquées',
    source           VARCHAR(30)    DEFAULT 'SIMULATEUR',
    -- Paramètres utilisés (JSON pour les seuils modifiés)
    parametres_json  JSON           DEFAULT NULL,
    PRIMARY KEY (id_simulation),
    FOREIGN KEY (id_client)       REFERENCES CLIENT(id_client)             ON DELETE CASCADE  ON UPDATE CASCADE,
    FOREIGN KEY (id_sous_segment) REFERENCES SOUS_SEGMENT(id_sous_segment) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (id_utilisateur)  REFERENCES UTILISATEUR(id_utilisateur)   ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ─────────────────────────────────────────────────────────────────
-- INDEX
-- ─────────────────────────────────────────────────────────────────
CREATE INDEX idx_sim_client   ON SIMULATION(id_client);
CREATE INDEX idx_sim_date     ON SIMULATION(date_simulation);
CREATE INDEX idx_sim_segment  ON SIMULATION(id_sous_segment);
CREATE INDEX idx_client_marche ON CLIENT(id_marche);
CREATE INDEX idx_client_forme  ON CLIENT(forme_juridique);
CREATE INDEX idx_client_code   ON CLIENT(code_client);
CREATE INDEX idx_prof_cat      ON PROFESSION(categorie);

-- ═════════════════════════════════════════════════════════════════
-- DONNÉES DE RÉFÉRENCE
-- ═════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────
-- MARCHÉS OFFICIELS BIAT
-- PART et PRO sont maintenant SÉPARÉS
-- ─────────────────────────────────────────────────────────────────
INSERT INTO MARCHE (code_marche, libelle, description) VALUES
('PART',  'Particuliers',
 'Clients tunisiens résidents — Personnes physiques non professionnelles'),
('PRO',   'Professionnels',
 'Clients tunisiens résidents — Personnes physiques exerçant une activité professionnelle'),
('TRE',   'Tunisiens Résidents à l\'Étranger',
 'Tunisiens vivant à l\'étranger avec centre d\'intérêt en Tunisie'),
('ENR',   'Étrangers Non Résidents',
 'Étrangers non résidents en Tunisie — séjour ≤ 3 mois consécutifs');

-- ─────────────────────────────────────────────────────────────────
-- PROFESSIONS (Annexes 4 & 5 — Note PBD N°2023-06)
-- ─────────────────────────────────────────────────────────────────

-- Annexe 4 : Professionnels HG à potentiel
INSERT INTO PROFESSION (libelle, categorie, est_potentiel, est_liberal) VALUES
('Médecin généraliste',          'HG',             TRUE,  TRUE),
('Médecin spécialiste',          'HG',             TRUE,  TRUE),
('Médecin dentiste',             'HG',             TRUE,  TRUE),
('Médecin vétérinaire',          'HG',             TRUE,  TRUE),
('Pharmacien',                   'HG',             TRUE,  TRUE),
('Biologiste et assimilé',       'HG',             TRUE,  TRUE),
('Opticien-lunetier',            'HG',             TRUE,  FALSE),
('Avocat',                       'HG',             TRUE,  FALSE),
('Expert-comptable',             'HG',             TRUE,  TRUE),
('Ingénieur',                    'HG',             TRUE,  FALSE),
('Architecte et urbaniste',      'HG',             TRUE,  FALSE),

-- Annexe 5 : Autres professions libérales
('Médecin de la fonction publique','LIBERALE_AUTRE',FALSE, TRUE),
('Huissier / Notaire / Expert',  'LIBERALE_AUTRE', FALSE, TRUE),
('Conseiller et consultant',     'LIBERALE_AUTRE', FALSE, TRUE),
('Transitaire et commissionnaire','LIBERALE_AUTRE', FALSE, TRUE),
('Professions paramédicales',    'LIBERALE_AUTRE', FALSE, TRUE),

-- Salariés à potentiel (Affluent / TRE Premium)
('Magistrat',                    'SALARIE_POTENTIEL', FALSE, FALSE),
('Enseignant universitaire',     'SALARIE_POTENTIEL', FALSE, FALSE),
('Chef de mission diplomatique', 'SALARIE_POTENTIEL', FALSE, FALSE),
('Haut fonctionnaire',           'SALARIE_POTENTIEL', FALSE, FALSE),
('Pilote et officier de pont',   'SALARIE_POTENTIEL', FALSE, FALSE),

-- Autres professions courantes
('Salarié secteur privé',        'AUTRE', FALSE, FALSE),
('Fonctionnaire',                'AUTRE', FALSE, FALSE),
('Étudiant',                     'AUTRE', FALSE, FALSE),
('Commerçant',                   'AUTRE', FALSE, FALSE),
('Artisan',                      'AUTRE', FALSE, FALSE),
('Retraité',                     'AUTRE', FALSE, FALSE),
('Sans profession',              'AUTRE', FALSE, FALSE),
('Autre',                        'AUTRE', FALSE, FALSE);

-- ─────────────────────────────────────────────────────────────────
-- SOUS-SEGMENTS OFFICIELS (Note PBD N°2023-06)
-- ─────────────────────────────────────────────────────────────────

-- MARCHÉ PARTICULIERS (id=1)
INSERT INTO SOUS_SEGMENT (id_marche, libelle_segment, libelle_sous_segment, criteres, badge_couleur, ordre_affichage) VALUES
-- Haut de Gamme PART
(1,'Haut de Gamme','Fortunés',
 'Particulier · VRD ≥ 500 mD','#FFD700',1),
(1,'Haut de Gamme','Patrimoniaux',
 'Particulier · VRD ∈ [300,500[ mD','#FFD700',2),
(1,'Haut de Gamme','Affluent',
 'Particulier · âge ≥ 30 ans · MMM ≥ 4 mD OU VRD ∈ [100,300[ mD','#FFC107',3),
(1,'Haut de Gamme','Épargnants et déposants exclusifs HG',
 'Particulier · uniquement cptes épargne/dépôts · VRD ∈ [100,300[ mD','#FFC107',4),

-- Classe Moyenne PART
(1,'Classe Moyenne','Les Salariés',
 'Particulier · âge ≥ 30 ans · MMM ∈ [1,4[ mD OU VRD ∈ [5,100[ mD','#4CAF50',5),
(1,'Classe Moyenne','Épargnants / déposants exclusifs CM',
 'Particulier · uniquement cptes épargne/dépôts · VRD ∈ [15,100[ mD','#66BB6A',6),
(1,'Classe Moyenne','Épargnants et déposants exclusifs CM',
 'Particulier · MMM ∈ [5,100[ · VRD ∈ [15,200[ mD','#4CAF50',7),

-- Grand Public PART
(1,'Grand Public','Particuliers',
 'Particulier · MMM < 1 mD · VRD < 5 mD · Secteur public','#2196F3',8),
(1,'Grand Public','Épargnants GP',
 'Particulier · uniquement épargne/dépôts · VRD < 5 mD','#2196F3',9),
(1,'Grand Public','Clients dormants',
 'Particulier · nb_operations_12m = 0 (aucun mouvement sur 1 an)','#9E9E9E',10),

-- Les Jeunes PART
(1,'Les Jeunes','Enfants et Élèves',
 'Particulier · âge ≤ 18 ans','#9C27B0',11),
(1,'Les Jeunes','Étudiants',
 'Particulier · 18 < âge ≤ 30 ans · Profession = Étudiant','#9C27B0',12),
(1,'Les Jeunes','JDA Potentiel',
 'Particulier · 18 < âge ≤ 30 ans · Profession à potentiel (Annexe 4)','#9C27B0',13),
(1,'Les Jeunes','Autres JDA',
 'Particulier · 18 < âge ≤ 30 ans · Autres professions · MMM < 10 mD','#AB47BC',14);

-- MARCHÉ PROFESSIONNELS (id=2)
INSERT INTO SOUS_SEGMENT (id_marche, libelle_segment, libelle_sous_segment, criteres, badge_couleur, ordre_affichage) VALUES
-- Haut de Gamme PRO
(2,'Haut de Gamme','Professionnels HG',
 'Professionnel · Profession à potentiel (Annexe 4) · VRD ≥ 200 mD','#FFD700',1),
(2,'Haut de Gamme','Patrimoniaux PRO',
 'Professionnel · VRD ∈ [300,500[ mD','#FFD700',2),
(2,'Haut de Gamme','Professions Libérales HG',
 'Professionnel · Profession libérale stratégique (Annexe 5) · VRD ∈ [100,300[ mD','#D4AF37',3),
(2,'Haut de Gamme','Épargnants et déposants exclusifs PRO HG',
 'Professionnel · uniquement cptes épargne/dépôts · VRD ∈ [100,300[ mD','#FFC107',4),

-- Classe Moyenne PRO
(2,'Classe Moyenne','Commerçants & Artisans CM',
 'Professionnel · MMM ∈ [1,5[ mD','#4CAF50',5),
(2,'Classe Moyenne','Épargnants PRO CM',
 'Professionnel · uniquement épargne/dépôts · VRD ∈ [15,100[ mD','#66BB6A',6),

-- Grand Public PRO
(2,'Grand Public','Commerçants & Artisans GP',
 'Professionnel · MMM < 1 mD','#2196F3',7),
(2,'Grand Public','Clients dormants PRO',
 'Professionnel · nb_operations_12m = 0 (aucun mouvement sur 1 an)','#9E9E9E',8);

-- MARCHÉ TRE (id=3)
INSERT INTO SOUS_SEGMENT (id_marche, libelle_segment, libelle_sous_segment, criteres, badge_couleur, ordre_affichage) VALUES
(3,'TRE','Premium',
 'TRE · Profession à potentiel OU MMM ≥ 25 mD OU VRD ≥ 50 mD','#FF5722',1),
(3,'TRE','Potentiel moyen',
 'TRE · MMM ∈ [1,25[ mD OU VRD ∈ [25,50[ mD','#FF7043',2),
(3,'TRE','Faible potentiel',
 'TRE · MMM < 1 mD ET VRD < 25 mD · compte actif','#FF8A65',3),
(3,'TRE','TRE Inactif',
 'TRE · nb_operations_12m = 0 (aucun mouvement sur 1 an)','#BDBDBD',4);

-- MARCHÉ ENR (id=4)
INSERT INTO SOUS_SEGMENT (id_marche, libelle_segment, libelle_sous_segment, criteres, badge_couleur, ordre_affichage) VALUES
(4,'ENR','Premium',
 'ENR · MMM ≥ 10 mD OU VRD ≥ 60 mD','#00796B',1),
(4,'ENR','Potentiel moyen',
 'ENR · MMM ∈ [5,10[ mD OU VRD ∈ [30,60[ mD','#00897B',2),
(4,'ENR','Faible potentiel',
 'ENR · MMM < 5 mD ET VRD < 30 mD · compte actif','#26A69A',3),
(4,'ENR','ENR Inactif',
 'ENR · nb_operations_12m = 0 (aucun mouvement sur 1 an)','#BDBDBD',4);

-- Utilisateur de test
INSERT INTO UTILISATEUR (nom_prenom, email, role, agence) VALUES
('Administrateur BIAT', 'admin@biat.com.tn', 'Admin', 'Siège Social');

-- ─────────────────────────────────────────────────────────────────
-- VUES UTILES
-- ─────────────────────────────────────────────────────────────────

-- Vue : Distribution des segments (dernière simulation par client)
CREATE OR REPLACE VIEW VUE_DISTRIBUTION_SEGMENTS AS
SELECT
    m.libelle               AS marche,
    ss.libelle_segment      AS segment,
    ss.libelle_sous_segment AS sous_segment,
    ss.badge_couleur,
    COUNT(DISTINCT s.id_client) AS nb_clients,
    AVG(s.mmm_utilise)      AS mmm_moyen,
    AVG(s.vrd_utilise)      AS vrd_moyen,
    AVG(s.age_utilise)      AS age_moyen
FROM SIMULATION s
JOIN SOUS_SEGMENT ss ON s.id_sous_segment = ss.id_sous_segment
JOIN MARCHE m        ON ss.id_marche      = m.id_marche
WHERE s.id_simulation IN (
    SELECT MAX(id_simulation) FROM SIMULATION GROUP BY id_client
)
GROUP BY m.libelle, ss.libelle_segment, ss.libelle_sous_segment, ss.badge_couleur
ORDER BY nb_clients DESC;

-- Vue : Clients dormants automatiques
CREATE OR REPLACE VIEW VUE_CLIENTS_DORMANTS AS
SELECT
    c.code_client,
    c.age,
    c.forme_juridique,
    p.libelle        AS profession,
    m.libelle        AS marche,
    df.mmm,
    df.vrd,
    df.nb_operations_12m,
    df.est_actif,
    df.date_maj
FROM CLIENT c
JOIN DONNEES_FINANCIERES df ON c.id_client    = df.id_client
JOIN MARCHE m               ON c.id_marche    = m.id_marche
LEFT JOIN PROFESSION p      ON c.id_profession= p.id_profession
WHERE df.nb_operations_12m = 0;

-- ─────────────────────────────────────────────────────────────────
-- PROCÉDURE : Statistiques générales
-- ─────────────────────────────────────────────────────────────────
DELIMITER //
CREATE PROCEDURE SP_STATS_GENERALES()
BEGIN
    SELECT 'MARCHE'          AS table_name, COUNT(*) AS nb_lignes FROM MARCHE
    UNION ALL
    SELECT 'SOUS_SEGMENT',    COUNT(*) FROM SOUS_SEGMENT
    UNION ALL
    SELECT 'PROFESSION',      COUNT(*) FROM PROFESSION
    UNION ALL
    SELECT 'CLIENT',          COUNT(*) FROM CLIENT
    UNION ALL
    SELECT 'DONNEES_FIN.',    COUNT(*) FROM DONNEES_FINANCIERES
    UNION ALL
    SELECT 'SIMULATION',      COUNT(*) FROM SIMULATION
    UNION ALL
    SELECT 'UTILISATEUR',     COUNT(*) FROM UTILISATEUR;
END //
DELIMITER ;

-- Vérification finale
CALL SP_STATS_GENERALES();
