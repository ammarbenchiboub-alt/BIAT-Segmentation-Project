# Documentation du projet - Segmentation client BIAT

## 1. Presentation
Application web (Streamlit) de simulation de segmentation de la clientele PBD
de la BIAT, destinee aux conseillers. Reproduit un outil bancaire reel.

## 2. Objectifs
Simulation individuelle, import CSV en masse, segmentation automatique,
chatbot expert, tableau de bord, assistant IA d'aide a la decision,
parametrage des regles metier.

## 3. Contexte metier
Nouvelle segmentation issue de la Note BIAT 2023-06 (clientele PBD). Marches
PART, PRO, TRE, ENR. Segments Haut de Gamme, Classe Moyenne, Grand Public,
Les Jeunes, et pour TRE/ENR Premium / Potentiel moyen / Faible potentiel.

## 4. Architecture
Projet modulaire : app.py + core, validation, segmentation, chatbot,
assistant, dashboard, ui, templates, config, data, tests. Le moteur unique
est le seul point de decision.

## 5. Base de donnees
Historique de session en memoire (DataFrame). Prevu pour evoluer vers un
Data Warehouse + Data Marts coherents avec les segments.

## 6. Data Warehouse
Table de faits "segmentations" (profil + segment + sous-segment + regle +
horodatage). Dimensions : marche, segment, sous-segment, profession.

## 7. Data Marts
Vues agregees par marche et par segment pour le pilotage commercial.

## 8. Moteur de segmentation
`core/engine.py`. Evaluation des regles par priorite ; premiere regle
satisfaite retenue. Combinaison MMM/VRD en OU. Renvoie segment, sous-segment,
regle appliquee et trace d'explication.

## 9. Regles metier
`config/regles_segmentation.json`. Seuils en DT. Listes de professions
(annexes 4 et 5). Source unique, aucune regle inventee.

## 10. Simulation individuelle
Formulaire 7 champs -> moteur -> carte segment + assistant IA sous le
resultat.

## 11. Import CSV
Modele Excel (listes deroulantes), validation, lignes invalides, segmentation
en masse, export CSV.

## 12. Chatbot Expert
Base de connaissances issue de la note + appel du moteur pour l'aide a la
decision. Message d'absence si l'information n'existe pas.

## 13. Assistant IA
Post-traitement automatique : coherence, contradictions, proximite de seuils,
score de confiance, alertes, recommandations. Ne modifie jamais le segment.

## 14. Tableau de bord
KPI (nombre de simulations, taux de segmentation), repartition par segment,
sous-segment et marche.

## 15. Parametrage
Edition des seuils et des listes de professions via l'interface, sans code.

## 16. Technologies utilisees
Python, Streamlit, pandas, openpyxl, scikit-learn (module ML complementaire),
SQLite (journal d'audit, gouvernance, tentatives de connexion). Dependances
figees dans requirements.txt (versions exactes) pour la reproductibilite.

## 17. Structure des fichiers
Voir README.md.

## 18. Installation
`pip install -r requirements.txt` puis `streamlit run app.py`.

## 19. Deploiement
Streamlit Community Cloud, ou serveur interne (streamlit run derriere un
reverse proxy). Variables et fichiers de regles versionnes.

## 20. Journal des evolutions
- v1.0.0 : moteur unique, 4 marches, simulateur, import CSV, chatbot,
  assistant IA, dashboard, parametrage. Regles extraites de la note 2023-06.
- v2.0.0 : renforcement technique SANS aucune modification des regles metier
  ni des resultats de segmentation (non-regression verifiee sur 715 008
  profils, empreinte SHA-256 identique a la v1.0.0).
  - Audit : ancre d'integrite externe (audit/ancre.json) detectant la
    suppression des dernieres entrees, que le seul chainage de hash ne voyait
    pas ; durabilite SQLite renforcee (journal_mode=DELETE + synchronous=FULL).
  - Securite : protection contre la force brute (verrouillage configurable,
    deverrouillage automatique, journalisation), comparaison a temps constant,
    protection contre l'enumeration des comptes.
  - Gouvernance : application des changements de regles rendue
    transactionnelle (tout-ou-rien) avec rollback automatique.
  - Performances : mise en cache du moteur (@st.cache_resource) invalidee
    automatiquement, et uniquement, quand les regles changent.
  - Qualite : dependances figees, tests etendus (auth, audit, gouvernance,
    cache), depot nettoye (docs/, .gitignore).
  Detail complet : voir README.md.
