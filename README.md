# BIAT - Application de segmentation client (Note 2023-06)

Application web professionnelle (Python + Streamlit) de simulation de la
segmentation de la clientele PBD de la BIAT. Elle reproduit un outil de
conseiller bancaire et s'appuie sur un **moteur unique** qui applique
strictement les regles de la Note BIAT 2023-06.

## Principes
- **Un seul moteur** (`core/engine.py`). Simulateur, import CSV, chatbot et
  assistant IA l'appellent tous. Aucune logique de segmentation dupliquee.
- **Regles centralisees** dans `config/regles_segmentation.json` (source
  unique, issue exclusivement de la note). Aucune regle inventee.
- **MMM OU VRD** : combinaison en OU logique (OR), jamais un ET.
- Marches geres : **PART, PRO, TRE, ENR** (TPME non gere).
- Champs de simulation : Marche, Profession, Age, MMM, VRD, Nationalite,
  Residence. Revenus et Nombre d'operations ne sont pas utilises.

## Installation
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Comptes de demonstration

L'application demande desormais une connexion. Comptes crees automatiquement
au premier lancement (fichier `auth/utilisateurs.json`) :

| Identifiant   | Mot de passe   | Role       |
|---------------|----------------|------------|
| conseiller1   | conseiller123  | Conseiller |
| admin1        | admin123       | Admin      |
| admin2        | admin456       | Admin      |
| auditeur1     | auditeur123    | Auditeur   |

Deux comptes admin existent expres : le workflow de double validation des
seuils (page Parametrage) exige qu'un second administrateur confirme ce
qu'un premier a propose.

## Fonctionnalites
- **Simulation individuelle** : segmentation d'un client + assistant IA
  automatique sous le resultat (coherence, alertes, score de confiance) +
  analyse Machine Learning complementaire (detection d'anomalies).
- **Import CSV** : modele Excel avec listes deroulantes, validation,
  detection des lignes invalides, segmentation en masse, export, analyse ML.
- **Chatbot Expert** : repond a partir de la note et du moteur ; aide a la
  decision sur un profil ; message d'absence si l'info n'existe pas.
- **Tableau de bord** : KPI, repartition par segment / sous-segment / marche,
  indicateurs Machine Learning (anomalies, confiance).
- **Parametrage** (role Admin) : modification des seuils et des listes de
  professions, avec simulation d'impact avant validation et double
  validation (un admin propose, un second confirme). Historique des
  versions du fichier de regles avec possibilite de restauration.
- **Journal d'audit** (roles Admin/Auditeur) : tracabilite complete et
  infalsifiable (chainage par hash) de chaque segmentation.

## Architecture
```
app.py                     Point d'entree Streamlit (navigation + pages)
config/regles_segmentation.json   Regles (source unique)
config/versions/           Historique horodate des regles
core/        engine.py (MOTEUR UNIQUE) + rules_loader.py + ml_anomaly.py
auth/        authentification locale (comptes, roles)
audit/       journal d'audit persistant (SQLite, chaine par hash)
gouvernance/ double validation des seuils + simulation d'impact + versions
validation/  controle des donnees
segmentation/ import CSV en masse (appelle le moteur)
chatbot/     chatbot expert metier
assistant/   assistant IA de coherence
dashboard/   KPI et repartitions
ui/          theme premium (CSS, entete, cartes)
templates/   generateur du modele Excel
data/        note de reference + exemple d'import
tests/       tests du moteur
```

## Tests
```bash
PYTHONPATH=. python tests/test_moteur.py
```

## Note
Le logo officiel est dans `assets/logo_biat.png` (utilise automatiquement
partout). Voir `_notes_conflits` dans le JSON pour les points de la note a
valider (ambiguites OCR).
