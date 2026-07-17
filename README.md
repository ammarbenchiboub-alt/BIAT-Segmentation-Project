# BIAT - Application de segmentation client (Note 2023-06)

Application web professionnelle (Python + Streamlit) de simulation de la
segmentation de la clientele PBD de la BIAT. Elle reproduit un outil de
conseiller bancaire et s'appuie sur un **moteur unique** qui applique
strictement les regles de la Note BIAT 2023-06.

> **Version 2.0** — Renforcement de la robustesse, de la securite et des
> performances. **Les regles metier et les resultats de segmentation sont
> strictement inchangés** : la non-regression est verifiee sur 715 008 profils
> (voir [Tests](#tests)).

## Principes

- **Un seul moteur** (`core/engine.py`). Simulateur, import CSV, chatbot et
  assistant IA l'appellent tous. Aucune logique de segmentation dupliquee.
- **Regles centralisees** dans `config/regles_segmentation.json` (source
  unique, issue exclusivement de la note). Aucune regle inventee.
- **MMM OU VRD** : combinaison en OU logique (OR), jamais un ET.
- Marches geres : **PART, PRO, TRE, ENR** (TPME non gere).
- Champs de simulation : Marche, Profession, Age, MMM, VRD, Nationalite,
  Residence (+ 8e champ optionnel `EpargnantDeposantExclusif`).
  Revenus et Nombre d'operations ne sont pas utilises.

## Installation

```bash
pip install -r requirements.txt
streamlit run app.py
```

Les dependances sont **figees** (`==`) pour garantir un environnement
reproductible et proteger le modele ML serialise. Voir
[Reproductibilite](#reproductibilite-des-dependances).

## Comptes de demonstration

L'application demande une connexion. Comptes crees automatiquement au premier
lancement (fichier `auth/utilisateurs.json`, non versionne) :

| Identifiant   | Mot de passe   | Role       |
|---------------|----------------|------------|
| conseiller1   | conseiller123  | Conseiller |
| admin1        | admin123       | Admin      |
| admin2        | admin456       | Admin      |
| auditeur1     | auditeur123    | Auditeur   |

Deux comptes admin existent expres : le workflow de double validation des
seuils exige qu'un second administrateur confirme ce qu'un premier a propose.

---

# Architecture

```
app.py                            Point d'entree Streamlit (navigation + pages)
config/regles_segmentation.json   Regles (SOURCE UNIQUE)
config/versions/                  Historique horodate des regles
commun/      socle technique (ouverture SQLite durable) -- sans metier
core/        engine.py (MOTEUR UNIQUE) + rules_loader.py + ml_anomaly.py
auth/        authentification locale + protection force brute
audit/       journal d'audit persistant (SQLite, chaine par hash + ancre)
gouvernance/ double validation, simulation d'impact, versions, transactionnel
validation/  controle des donnees
segmentation/ import CSV en masse (appelle le moteur)
chatbot/     chatbot expert metier
assistant/   assistant IA de coherence
dashboard/   KPI et repartitions
ui/          theme premium (CSS, entete, cartes)
templates/   generateur du modele Excel
data/        note de reference + exemple d'import
docs/        documentation et fiches de competences
tests/       tests (moteur, auth, audit, gouvernance, cache, concurrence, ML)
```

## Regle d'or : le sens des dependances

```
                  config/regles_segmentation.json
                              |
                        core/rules_loader
                              |
                        core/engine  <--- MOTEUR UNIQUE, ne depend de RIEN d'autre
                              |
        +---------+-----------+-----------+---------+
        |         |           |           |         |
   simulateur  import CSV  chatbot   assistant  dashboard
```

- `core/engine.py` **n'importe aucun** des autres modules applicatifs, ni
  scikit-learn, ni numpy.
- `core/ml_anomaly.py` **n'importe jamais** `core/engine.py` : le module ML est
  structurellement incapable d'influencer une segmentation.
- `import core` **ne charge pas** le module ML : le moteur reste utilisable et
  testable sans la pile scikit-learn.
- `audit/`, `auth/`, `gouvernance/` sont independants du moteur : ils
  enregistrent ou encadrent des decisions, ils n'en prennent aucune.
- `commun/` ne contient que du technique (ouverture SQLite) : aucun seuil,
  aucun segment, aucune regle. Il est donc importable par toutes les couches
  sans jamais creer de dependance vers le metier.

Ces regles ne sont pas seulement documentees : `tests/test_ml.py` les verifie
(echec du test si `engine.py` se met a importer le module ML, par exemple).

---

# Moteur de segmentation

`core/engine.py` — **unique point de decision de toute l'application.**

- Les regles du marche sont triees par `priorite` ; la **premiere regle
  satisfaite** est retenue.
- Chaque regle enchaine : filtre profession (ET) -> filtre epargnant exclusif
  (ET) -> filtre age (ET) -> **condition monetaire MMM OU VRD (OU)**.
- Convention des bornes : `min` inclusif (`>=`), `max` exclusif (`<`).
- Renvoie un `ResultatSegmentation` : segment, sous-segment, regle appliquee,
  succes, et **trace d'explication** de l'evaluation.
- Aucune regle n'est ecrite en dur : tout vient du JSON.

> ⚠️ **Interdiction absolue** : ne jamais creer une seconde logique de
> segmentation ailleurs. Toute nouvelle fonctionnalite appelle `segmenter()`.

---

# Systeme d'audit

`audit/journal.py` — tracabilite opposable des decisions : *qui a segmente
quel profil, quand, avec quel resultat, et avec quelle version des regles.*

## Garanties

- **Persistant** (SQLite) : survit a la fermeture de l'application, contrairement
  a l'historique de session.
- **Append-only** : le module n'expose **aucune** fonction de modification ou de
  suppression. Seule l'insertion existe.
- **Chaine par hash** : chaque entree contient le hash de la precedente et un
  hash d'elle-meme.
- **Ancre d'integrite externe** (`audit/ancre.json`, **hors** de la base) :
  conserve le nombre d'entrees attendu et le hash de la derniere entree.
- **Version des regles** tracee a chaque decision (empreinte SHA-256 du JSON).

## Pourquoi une ancre externe

Le chainage seul **ne detecte pas la suppression des dernieres entrees**
(*tail truncation*) : supprimer les N derniers enregistrements laisse une
chaine parfaitement valide depuis la genese, car rien dans la base ne dit
combien d'entrees devraient exister. L'ancre, stockee **en dehors** de
`journal.sqlite3`, comble cet angle mort.

| Attaque                             | Detectee par                  |
|-------------------------------------|-------------------------------|
| Modification d'une entree           | recalcul du hash de l'entree  |
| Reorganisation des entrees          | chainage `hash_precedent`     |
| Suppression au milieu               | chainage `hash_precedent`     |
| **Suppression des dernieres**       | **ancre externe**             |
| **Ajout d'entrees hors application**| **ancre externe**             |
| Tronquage + compteur d'ancre falsifie | hash de fin de l'ancre      |

Verification via la page **Journal d'audit** -> *Verifier l'integrite*.

## Durabilite

`journal_mode=DELETE` + `synchronous=FULL` (au lieu de `MEMORY`) : une
transaction interrompue est annulee proprement plutot que de corrompre la
base, et une entree confirmee est reellement ecrite sur le disque. WAL a ete
ecarte : ses fichiers `-wal`/`-shm` sont precisement ce qui echoue sur les
partages reseau. Repli automatique sur `MEMORY` si l'environnement refuse le
mode durable.

Configuration definie **une seule fois** dans `commun/base_sqlite.py`, pour les
trois bases (audit, gouvernance, tentatives). Elle etait auparavant recopiee
dans chaque module, et les copies avaient diverge : la base de gouvernance
etait restee en `MEMORY`, donc non durable.

---

# Concurrence

Streamlit sert **chaque session dans un thread du meme processus** : deux
conseillers qui utilisent l'application au meme instant executent reellement le
meme code en parallele. Ce n'est pas un cas theorique.

Deux protections, complementaires, sur chaque cycle « lire un etat puis
l'ecrire » :

| Mecanisme | Portee | Ce qu'il empeche |
|---|---|---|
| `threading.Lock` | threads du processus Streamlit | le cas reel et frequent |
| `BEGIN IMMEDIATE` | processus distincts | 2e instance, script de maintenance |

`BEGIN IMMEDIATE` est indispensable : sans lui, SQLite n'acquiert le verrou
d'ecriture qu'au **premier INSERT**, donc **apres** la lecture preparatoire —
la fenetre de course resterait ouverte.

Defauts corriges (chacun couvert par `tests/test_concurrence.py`) :

- **Fourche de la chaine d'audit** : deux ecrivains simultanes lisaient le meme
  `hash_precedent` et produisaient deux entrees referencant le meme parent —
  alteration **irreversible**, signalee ensuite a tort comme une falsification.
- **Ecritures concurrentes impossibles** : 19 sur 20 echouaient
  (`PermissionError`), toutes les ecritures de l'ancre passant par un meme
  fichier temporaire. Le nom du temporaire inclut desormais PID et thread.
- **Compteur d'echecs non deterministe** : 20 tentatives paralleles n'en
  comptabilisaient que 10 (mises a jour perdues). Un compteur de securite dont
  le resultat depend du timing n'en est pas un.
- **Double validation appliquee deux fois** : deux administrateurs confirmant
  au meme instant validaient tous deux la meme proposition (TOCTOU entre la
  lecture du statut et sa mise a jour), produisant deux versions archivees et
  deux entrees d'audit pour un seul acte de gouvernance.

---

# Gouvernance des regles

## Maker-Checker (double validation)

Aucun changement de seuil n'est applique directement :

1. un administrateur **propose** un changement (avec justification) ;
2. la **simulation d'impact** rejoue les profils reels du journal a travers les
   regles proposees et chiffre combien de clients changeraient de segment ;
3. un **SECOND** administrateur confirme — `workflow_seuils.confirmer()`
   **refuse** qu'un compte confirme sa propre proposition (separation des
   taches) ;
4. le changement est applique, versionne et trace.

La **restauration** d'une version anterieure n'echappe pas a la regle : elle
cree une nouvelle proposition, a confirmer comme n'importe quelle autre.

## Application transactionnelle

`gouvernance/application_regles.py` — l'application d'une proposition est
**tout-ou-rien**. Les quatre etapes etaient auparavant enchainees sans filet
dans `app.py` ; une erreur au milieu laissait un etat incoherent (regles
appliquees sans trace d'audit, ou proposition validee sans effet).

| # | Etape                        | Annulation                     |
|---|------------------------------|--------------------------------|
| 1 | Confirmer la proposition     | `rouvrir` -> EN_ATTENTE        |
| 2 | Ecrire les regles (atomique) | restauration de l'octet pres   |
| 3 | Enregistrer la version       | `supprimer_version`            |
| 4 | Ecrire le journal d'audit    | **aucune** (append-only)       |

L'ordre n'est pas arbitraire : le journal d'audit est **irreversible**, donc
il passe **en dernier**. Toute etape faillible est tentee avant lui. S'il
echoue, les trois precedentes sont annulees et l'operation est sans effet —
il ne reste alors aucune modification a tracer.

Le fichier de regles est ecrit via fichier temporaire + `os.replace`
(atomique) : une coupure ne peut jamais laisser un JSON tronque, qui rendrait
l'application inutilisable.

---

# Authentification

`auth/utilisateurs.py` + `auth/tentatives.py`

- Mots de passe **jamais stockes en clair** : PBKDF2-HMAC-SHA256, 100 000
  iterations, **sel aleatoire par utilisateur**.
- Comparaison a **temps constant** (`hmac.compare_digest`).
- **Anti-enumeration** : un compte inexistant declenche un calcul de hash
  factice, pour que le temps de reponse ne revele pas quels comptes existent.
- **RBAC** : Conseiller / Admin / Auditeur, applique en *defense en profondeur*
  (page retiree du menu **et** acces re-controle en tete de page).

## Protection contre la force brute

| Parametre                | Defaut | Variable d'environnement      |
|--------------------------|--------|-------------------------------|
| Tentatives avant verrou  | 5      | `BIAT_MAX_TENTATIVES`         |
| Duree du verrouillage    | 15 min | `BIAT_VERROUILLAGE_MINUTES`   |

- Verrouillage **par identifiant**, applique **meme aux comptes inexistants**
  (sinon le verrouillage revelerait quels comptes existent).
- **Deverrouillage automatique** : aucune intervention d'administrateur.
- **Temps restant affiche** a l'utilisateur.
- **Remise a zero** immediate apres une connexion reussie.
- **Journalisation** de chaque tentative echouee (persistante).
- Compteur **persistant** (SQLite) : rouvrir un onglet ne le remet pas a zero.

Point d'entree applicatif : `auth.authentifier()`. L'API historique
`verifier_identifiants()` est **conservee inchangee**.

---

# Cache

Streamlit reexecute tout `app.py` a chaque interaction. Sans cache, chaque
rerun relisait le JSON et reconstruisait moteur, chatbot et assistant.

```python
@st.cache_resource(show_spinner=False)
def _construire_moteur(empreinte: str) -> MoteurSegmentation:
    return MoteurSegmentation()

def get_moteur() -> MoteurSegmentation:          # API inchangee
    return _construire_moteur(empreinte_regles())
```

La clef de cache est l'**empreinte SHA-256 du contenu** de
`regles_segmentation.json` (`core.rules_loader.empreinte_regles`) :

- regles inchangees -> empreinte stable -> **une seule instance** reutilisee ;
- regles modifiees -> empreinte differente -> **reconstruction automatique**.

L'invalidation est donc exacte, et **aucun appel manuel a `.clear()` n'est
necessaire** : impossible d'oublier d'invalider le cache. Le contenu est
prefere au `mtime` (deux ecritures dans la meme seconde laisseraient un cache
perime ; une simple recopie provoquerait une reconstruction inutile).

C'est aussi cette empreinte qui identifie la version des regles dans le
journal d'audit : **une seule definition** de « version des regles » dans
toute l'application.

## Autres optimisations

| Chemin | Avant | Apres | Facteur |
|---|---|---|---|
| Analyse ML d'un import (5 000 lignes) | 73,4 s | 0,18 s | **×400** |
| Import CSV complet (5 000 lignes) | 74,4 s | 1,37 s | **×54** |
| Journalisation d'un lot (300 lignes) | 8,31 s | 0,06 s | **×138** |
| Moteur / chatbot / assistant par rerun | reconstruits | mis en cache | — |

- **Analyse ML vectorisee** : `analyser_dataframe` appelait le modele **ligne
  par ligne** (`df.iterrows()`), reconstruisant un DataFrame d'une ligne a
  chaque fois, et calculait des explications textuelles aussitot jetees. Un
  seul appel suffit : Isolation Forest note chaque ligne independamment des
  autres. Resultats **identiques au bit pres** (verifie par `tests/test_ml.py`,
  et non suppose).
- **Journalisation par lot** : un import ecrit desormais toutes ses entrees en
  **une transaction**, avec **une** lecture du fichier de regles et **une**
  ecriture d'ancre. Auparavant : un `fsync` et une relecture du JSON **par
  ligne**.

---

# Securite — synthese

| Domaine        | Mesure                                                        |
|----------------|---------------------------------------------------------------|
| Mots de passe  | PBKDF2-HMAC-SHA256, 100 000 iterations, sel par utilisateur    |
| Comparaison    | temps constant (`hmac.compare_digest`)                        |
| Force brute    | verrouillage 5 essais / 15 min, auto-deverrouillage, journalise |
| Enumeration    | hash factice + verrouillage des comptes inexistants           |
| Acces          | RBAC 3 roles, defense en profondeur                           |
| Tracabilite    | journal append-only, chaine par hash + ancre externe          |
| Durabilite     | `journal_mode=DELETE` + `synchronous=FULL`                    |
| Concurrence    | verrou de thread + `BEGIN IMMEDIATE` sur tout cycle lire/ecrire |
| Separation     | Maker-Checker, auto-confirmation impossible (meme en parallele) |
| Coherence      | application des regles transactionnelle avec rollback         |
| Secrets        | comptes et bases jamais versionnes (`.gitignore`)             |

## Comportement en cas de panne du journal (choix delibere)

Si le journal d'audit ne peut pas ecrire, la segmentation **echoue** au lieu
d'etre affichee sans trace. C'est un choix : en contexte bancaire, une decision
non tracee vaut moins qu'une decision refusee. La consequence est assumee — un
journal indisponible bloque l'application.

## Limites connues (assumees)

- **Comptes locaux** : en banque reelle, remplacer par une federation
  d'identite (OIDC/SAML sur l'AD) avec **MFA** pour les roles admin/auditeur.
- **Comptes de demonstration** a remplacer des le premier deploiement reel.
- **Ancre d'integrite locale** : un attaquant disposant d'un acces en ecriture
  au **systeme de fichiers complet** peut alterer journal *et* ancre de facon
  coherente. Une protection totale exige un temoin **hors du serveur** (journal
  repliqué, horodatage tiers, ou stockage WORM).
- **Portee de l'ancre** : les entrees anterieures a son introduction ne sont
  couvertes contre le tronquage qu'a partir de son initialisation. Le chainage,
  lui, couvre tout l'historique.
- **Verrouillage par compte** (et non par IP) : adapte a un deploiement interne
  ou l'IP vue par l'application n'est pas fiable. Un attaquant peut encore
  verrouiller volontairement un compte (deni de service cible).
- **Concurrence multi-processus** : le verrou de thread ne couvre qu'un
  processus ; `BEGIN IMMEDIATE` prend le relais entre processus. Un deploiement
  reellement multi-instances (plusieurs serveurs, base partagee) exigerait un
  SGBD serveur (PostgreSQL) plutot que SQLite.
- **`verifier_integrite()` charge tout le journal en memoire** : sans effet aux
  volumes vises (quelques milliers d'entrees), a revoir en lecture par blocs
  au-dela de ~100 000 entrees.
- **Re-segmentation a chaque rerun** : tant qu'un fichier reste charge dans la
  page Import CSV, il est re-segmente a chaque interaction (~1,4 s pour 5 000
  lignes, contre 74 s avant optimisation). Acceptable en l'etat ; un
  `@st.cache_data` sur le contenu du fichier l'eliminerait.

---

# Reproductibilite des dependances

`requirements.txt` fige les versions (`==`, releve sur Python 3.13) :

- **reproductibilite** : meme environnement aujourd'hui, ailleurs et dans deux
  ans — indispensable pour une application censee etre auditable ;
- **integrite du modele ML** : `core/ml_model/anomaly_pipeline.joblib` est un
  objet scikit-learn serialise ; le recharger avec une autre version de
  scikit-learn n'est pas supporte ;
- `numpy` est desormais **declare explicitement** (importe par
  `core/ml_anomaly.py`, il n'etait installe que par transitivite).

Apres toute montee de version : relancer `python tests/run_all.py`, et
reentrainer le modele si `scikit-learn` change (Tableau de bord -> *Reentrainer
le modele*).

---

# Tests

```bash
python tests/run_all.py          # toutes les suites
python tests/test_moteur.py      # une suite en particulier
```

Aucune dependance de test externe (pas de pytest) : ajouter une dependance
aurait contredit l'objectif de reproductibilite. Chaque suite est **isolee**
(dossier temporaire) et ne touche ni au journal, ni aux comptes, ni aux regles
reels.

| Suite                  | Couvre                                                    |
|------------------------|-----------------------------------------------------------|
| `test_moteur.py`       | non-regression metier : 31 cas issus des seuils de la note |
| `test_auth.py`         | hachage, verification, force brute, verrouillage, journal  |
| `test_audit.py`        | chaine, ancre, 8 scenarios d'alteration, durabilite        |
| `test_gouvernance.py`  | Maker-Checker, transactionnel, rollback sur panne injectee |
| `test_cache.py`        | stabilite et invalidation du cache, API inchangee          |
| `test_concurrence.py`  | ecritures paralleles, fourche de chaine, TOCTOU, perfs     |
| `test_ml.py`           | vectorisation a l'identique, accord de version, isolation  |

Les suites `test_concurrence.py` et `test_ml.py` sont nees de la revue
d'architecture : chaque cas y verrouille un defaut **reellement constate et
mesure**, pas un risque suppose.

## Non-regression du moteur

Toute modification technique doit laisser les resultats de segmentation
**strictement identiques**. La verification rejoue **715 008 profils**
(produit cartesien marches x professions x ages x MMM x VRD x 8e champ) et
compare l'empreinte SHA-256 de l'ensemble des resultats **et de leurs traces
d'explication**.

Empreinte de reference (v2.0, inchangee depuis la v1.0) :

```
19789b8424abaa4310f31128e74a98d624ebafb29015721aaee5d700b14754e8
```

---

# Organisation du projet

- **Journal de developpement** : [`docs/JOURNAL_DEVELOPPEMENT.md`](docs/JOURNAL_DEVELOPPEMENT.md)
  consigne, pour chaque modification, le probleme, l'analyse, la solution, sa
  justification technique, l'impact et les tests. C'est la source de reference
  pour le rapport de PFE, le memoire et la soutenance.
- **Versionne** : sources, `config/regles_segmentation.json`, `config/versions/`,
  le modele ML, `assets/logo_biat.png`, `data/`, `docs/`.
- **Non versionne** (regenere automatiquement, propre a chaque poste) :
  `auth/utilisateurs.json` (hash des mots de passe), `*.sqlite3` (journal,
  propositions, tentatives), `audit/ancre.json`, `__pycache__/`, fichiers
  temporaires et fichiers d'IDE.
- `docs/competences/` : fiches de competences du PFE (documentation, sans
  impact sur l'application).

## Note

Le logo officiel est dans `assets/logo_biat.png` (utilise automatiquement
partout). Voir `_notes_conflits` dans le JSON pour les points de la note a
valider (ambiguites OCR).
