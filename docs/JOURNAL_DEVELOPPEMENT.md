# Journal de developpement — Projet BIAT Segmentation 2.0

**Auteur** : Ammar Ben Chiboub
**Contexte** : Projet de Fin d'Etudes — Master Business Analytics
**Objet** : Application de simulation de la segmentation de la clientele PBD de
la BIAT, conforme a la Note interne 2023-06.

---

## Objet et portee de ce document

Ce journal consigne, de maniere chronologique et structuree, l'integralite des
modifications techniques apportees a l'application lors du passage de la
version 1.0 a la version 2.0. Chaque note suit une trame unique (probleme,
analyse, solution, justification, impact, compatibilite, tests, resultat) afin
de pouvoir etre reprise directement dans le rapport de PFE, le memoire, la
documentation technique et le support de soutenance.

### Principe directeur du projet

L'ensemble des travaux consignes ici obeit a une contrainte non negociable :

> **Aucune modification de la logique metier de segmentation.**
> Les regles issues de la Note BIAT 2023-06 constituent la reference
> reglementaire du projet. Le perimetre de la version 2.0 porte exclusivement
> sur la qualite technique : robustesse, securite, performances,
> maintenabilite. Le comportement fonctionnel de l'application doit rester
> **strictement identique**.

Cette contrainte n'est pas une declaration d'intention : elle est **verifiee
mecaniquement** avant et apres chaque modification par le protocole de
non-regression decrit dans la **Note 08**, qui compare l'empreinte
cryptographique des resultats de segmentation sur 715 008 profils.

### Conventions de redaction

- Les mesures de performance sont des **relevés réels**, effectues sur
  l'environnement de reference (Python 3.13.0, Windows 11), et non des
  estimations.
- Lorsqu'un defaut a ete introduit par une modification anterieure de ce meme
  projet, cela est **explicitement indique**. La demarche d'ingenierie consiste
  autant a detecter ses propres erreurs qu'a produire du code : les masquer
  appauvrirait la valeur pedagogique de ce journal.
- Chaque note se conclut par les tests qui **verrouillent** la correction,
  c'est-a-dire qui echoueraient si le defaut reapparaissait.

### Index des notes

| N° | Titre | Categorie |
|----|-------|-----------|
| 01 | Renforcement de la chaine d'audit : ancre d'integrite externe | Securite / Auditabilite |
| 02 | Durabilite du stockage SQLite | Robustesse |
| 03 | Protection contre les attaques par force brute | Securite |
| 04 | Application transactionnelle des changements de regles | Gouvernance / Robustesse |
| 05 | Mise en cache du moteur de segmentation | Performances |
| 06 | Reproductibilite de l'environnement d'execution | Qualite / Reproductibilite |
| 07 | Reorganisation et assainissement du depot | Maintenabilite |
| 08 | Strategie de tests et protocole de non-regression | Qualite logicielle |
| 09 | Refonte de la documentation technique | Maintenabilite |
| 10 | Correction des defauts de concurrence | Robustesse / Securite |
| 11 | Optimisation des traitements en masse | Performances |
| 12 | Coherence entre le modele ML livre et la version figee | Reproductibilite |
| 13 | Factorisation du socle d'acces aux donnees (DRY) | Architecture |
| 14 | Fiabilisation du chatbot expert : recherche et source unique | Correction / Gouvernance |

---
---

# Note 01 — Renforcement de la chaine d'audit : ancre d'integrite externe

## Probleme identifie

Le journal d'audit (`audit/journal.py`) enregistre chaque decision de
segmentation dans une base SQLite, en chainant les entrees par hachage
cryptographique : chaque enregistrement contient le hash de l'enregistrement
precedent ainsi qu'un hash de son propre contenu. Ce dispositif etait presente
comme rendant le journal « infalsifiable ».

L'audit de l'existant a etabli que cette qualification etait **surevaluee**. Le
chainage detecte effectivement la modification d'une entree et la suppression
d'une entree situee au milieu de l'historique, mais il **ne detecte pas la
suppression des dernieres entrees** (attaque dite de *tail truncation*).

## Analyse

La verification d'integrite recalcule la chaine depuis l'entree de genese
jusqu'a la derniere entree presente. Or, supprimer les *N* derniers
enregistrements produit une chaine qui reste **parfaitement coherente** : les
entrees restantes se referencent correctement, et aucun element interne a la
base ne permet de savoir combien d'entrees auraient du exister.

La cause structurelle est la suivante : **le temoin d'integrite et l'objet
qu'il protege residaient dans le meme fichier**. Un adversaire disposant d'un
acces en ecriture a `journal.sqlite3` pouvait donc supprimer la trace d'une
operation recente sans laisser aucun indice detectable.

**Risques encourus** :

- **Risque de conformite** : un journal d'audit dont on ne peut garantir
  l'exhaustivite ne possede aucune valeur probante en controle interne
  bancaire. La question a laquelle il doit repondre — « qui a segmente quel
  profil, quand, avec quelles regles ? » — devient sans reponse fiable.
- **Risque operationnel** : l'operation la plus interessante a effacer pour un
  acteur malveillant est precisement **la plus recente**, c'est-a-dire celle
  qui se trouve en fin de journal — exactement la zone non couverte.
- **Risque de fausse assurance** : plus grave que l'absence de controle, un
  controle qui affirme « journal intact » alors que des entrees ont ete
  supprimees induit l'auditeur en erreur.

## Solution retenue

Introduction d'une **ancre d'integrite externe** : un fichier
`audit/ancre.json`, stocke **en dehors** de la base SQLite, qui conserve deux
invariants apres chaque ecriture :

1. `nombre_entrees` — le nombre total d'entrees que le journal doit contenir ;
2. `dernier_hash` — le hash de la derniere entree ecrite.

La fonction `verifier_integrite()` effectue desormais **deux controles
complementaires**, dont aucun ne suffit seul :

| Controle | Portee | Detecte |
|---|---|---|
| Chainage interne | toute la chaine depuis la genese | modification, reorganisation, suppression au milieu |
| Ancre externe | bornes du journal | suppression des dernieres entrees, ajout non trace |

L'ecriture de l'ancre est **atomique** (fichier temporaire puis `os.replace`),
afin qu'une interruption ne laisse jamais une ancre tronquee — ce qui ferait
echouer a tort tous les controles ulterieurs.

Une fonction `assurer_ancre()` initialise l'ancre a partir de l'etat courant
lorsqu'elle est absente. Ce point est indispensable pour **conserver
l'historique existant** : le journal preexistait a l'introduction du mecanisme,
on ne pouvait donc pas exiger que l'ancre ait toujours ete presente.

## Justification technique

**Pourquoi un fichier externe plutot qu'une table supplementaire ?**
Placer le temoin dans une table de `journal.sqlite3` aurait reconduit exactement
le defaut d'origine : l'adversaire qui tronque le journal ajusterait le
compteur dans la meme transaction. La **separation physique du temoin et de
l'objet protege** est la propriete qui cree la valeur ; tout le reste en decoule.

**Pourquoi conserver aussi le hash de fin, et pas seulement le compteur ?**
Un compteur seul serait contourne par un adversaire qui supprime deux entrees
et corrige le nombre. Le hash de fin resiste a cette manœuvre : le recalculer
supposerait de disposer du contenu supprime. Les deux invariants forment donc
un controle a deux barrieres, dont la seconde suppose la connaissance de ce que
l'attaquant vient precisement de detruire.

**Pourquoi ne pas signer l'ancre (HMAC) ?**
Une signature deplacerait le probleme vers la **conservation de la clef** : sur
une installation mono-poste, la clef residerait sur le meme systeme de fichiers
que ce qu'elle protege, sans gain reel de securite. Cette limite est assumee et
documentee plutot que masquee par une complexite trompeuse (voir *Impact*).

**Pourquoi ecrire l'ancre apres le commit et non avant ?**
Les deux ordres laissent une fenetre d'incoherence. Ecrire l'ancre en premier
ferait apparaitre, en cas d'interruption, un journal **en retard** sur l'ancre —
indiscernable d'un tronquage, donc generateur de **faux positifs**. L'ordre
retenu produit l'anomalie inverse (journal en avance d'une entree), qui est
diagnostiquee distinctement et **n'entraine jamais de perte d'entree**. Entre
deux imperfections, on retient celle qui ne ment jamais dans le sens dangereux.

## Fichiers modifies

- `audit/journal.py` — ancre, ecriture atomique, refonte de `verifier_integrite`
- `audit/__init__.py` — exposition de `assurer_ancre`
- `.gitignore` — exclusion de `audit/ancre.json` (temoin local, non versionnable)
- `tests/test_audit.py` — suite de tests dediee (creation)

## Changements realises

- Ajout de `CHEMIN_ANCRE`, `_lire_ancre()`, `_ecrire_ancre()`, `assurer_ancre()`.
- Refonte de `verifier_integrite()` : au controle de chainage s'ajoute la
  confrontation a l'ancre, avec des messages **distinguant chaque anomalie**
  (entrees manquantes, entrees ajoutees, hash de fin divergent, ancre absente,
  ancre corrompue).
- Documentation d'une matrice de detection attaque → mecanisme dans l'en-tete
  du module.

## Impact

- **Securite** : couverture de la derniere famille d'alteration non detectee.
  Le journal passe d'« infalsifiable » (affirmation excessive) a « toute
  alteration connue est detectable, sous une hypothese explicite ».
- **Performances** : une ecriture de fichier supplementaire par lot d'ecriture.
  Negligeable (voir Note 11, qui a supprime le surcout par ligne).
- **Maintenabilite** : la matrice de detection documentee permet a un
  mainteneur de savoir ce que le dispositif couvre — et surtout ce qu'il ne
  couvre pas.
- **Robustesse** : l'ecriture atomique interdit l'ancre partiellement ecrite.
  L'absence d'ancre est signalee, jamais silencieusement ignoree.
- **Gouvernance** : le journal redevient opposable, condition de la valeur
  probante attendue en controle interne.
- **Experience utilisateur** : inchangee, hormis des messages de verification
  plus precis dans la page « Journal d'audit ».

## Compatibilite

Le module `audit/` est **structurellement independant** du moteur de
segmentation : il enregistre un resultat deja calcule et n'intervient jamais
dans son calcul. Aucune ligne de `core/engine.py` n'a ete modifiee. L'historique
existant (36 entrees) est conserve et verifie intact apres migration.

## Bonnes pratiques utilisees

- **Defense en profondeur** : deux controles independants couvrant des surfaces
  d'attaque disjointes.
- **Fail-safe** : en cas de doute (ancre absente ou corrompue), le systeme
  refuse de conclure a l'integrite plutot que de rassurer a tort.
- **Atomicite** (`os.replace`) : pattern *write-temp-then-rename*.
- **Honnetete de la documentation** : les limites sont enoncees dans le code
  lui-meme, au plus pres de l'implementation.

## Tests effectues

Suite `tests/test_audit.py` — **24 assertions**, dont **8 scenarios
d'alteration** rejoues sur un journal temporaire isole :

| Scenario | Resultat |
|---|---|
| Modification d'une entree | detecte (hash) |
| Suppression au milieu | detecte (chainage) |
| Reorganisation des entrees | detecte (chainage) |
| **Suppression des dernieres entrees** | **detecte (ancre)** |
| Tronquage + compteur d'ancre falsifie | detecte (hash de fin) |
| Ajout d'entrees hors application | detecte (ancre) |
| Ancre supprimee | signale, puis reinitialisee |
| Ancre corrompue | refus de conclure a l'integrite |

## Resultat

La chaine d'audit detecte desormais **l'ensemble des familles d'alteration
connues**. La seule limite subsistante — un adversaire disposant d'un acces en
ecriture au systeme de fichiers complet peut alterer journal *et* ancre de
maniere coherente — est **structurelle a toute solution mono-machine** et
documentee comme telle : sa levee exige un temoin hors serveur (replication,
horodatage par tiers de confiance, ou stockage WORM).

---
---

# Note 02 — Durabilite du stockage SQLite

## Probleme identifie

Les bases SQLite de l'application etaient ouvertes avec
`PRAGMA journal_mode=MEMORY`, choix motive dans un commentaire par des erreurs
« disk I/O error » observees sur des environnements de fichiers synchronises ou
reseau.

## Analyse

Le mode `MEMORY` conserve le **journal de rollback en memoire vive**. Sa
consequence est mal alignee avec l'usage : une interruption survenant pendant
une ecriture ne provoque pas un simple retour a l'etat anterieur, mais peut
laisser la base **corrompue**, le journal necessaire a l'annulation ayant
disparu avec le processus.

Pour un journal d'audit, dont la finalite meme est d'etre opposable, ce
compromis est inverse : on accepte un risque de **perte totale** pour gagner en
debit sur un usage a faible volume ou le debit n'est pas contraignant.

**Risques** : corruption de la base d'audit ou de gouvernance sur coupure
d'alimentation ou arret brutal ; perte d'entrees confirmees a l'utilisateur.

## Solution retenue

Passage a `journal_mode=DELETE` + `synchronous=FULL`, avec repli automatique sur
`MEMORY` si l'environnement refuse reellement le mode durable.

- `DELETE` : journal de rollback **sur disque** → une transaction interrompue
  est annulee proprement, jamais laissee a demi-ecrite.
- `synchronous=FULL` : `fsync` a chaque commit → une entree confirmee est
  reellement sur le disque.

## Justification technique

**Pourquoi avoir ecarte WAL (Write-Ahead Logging) ?**
WAL est generalement le mode recommande : plus rapide, meilleure concurrence en
lecture. Il a pourtant ete **rejete deliberement**. WAL s'appuie sur de la
memoire partagee materialisee par des fichiers `-wal` et `-shm`, et c'est
precisement ce mecanisme qui echoue sur les partages reseau et dossiers
synchronises — soit exactement l'environnement invoque a l'origine pour choisir
`MEMORY`. Adopter WAL aurait donc reintroduit le probleme initial en croyant le
resoudre.

`DELETE` est le seul mode a la fois **portable et durable** : il n'utilise que
le fichier de base et un journal classique.

**Cout assume** : environ 25 ms par commit (`fsync`). Acceptable tant que l'on
ne commit qu'une fois par action utilisateur. Cette condition a d'ailleurs ete
**violee** par la version initiale sur le chemin d'import en masse, ce qui a
produit une regression de performance majeure corrigee en **Note 11** — un
exemple concret de la maniere dont une decision localement correcte peut avoir
des consequences non anticipees sur un autre chemin d'execution.

**Pourquoi un repli plutot qu'une erreur ?** Une application qui refuse de
demarrer est un echec plus grave qu'un fonctionnement en mode degrade : l'ancre
externe (Note 01) continue, dans tous les cas, de detecter toute alteration.

## Fichiers modifies

- `audit/journal.py`, `auth/tentatives.py`, `gouvernance/workflow_seuils.py`
- puis `commun/base_sqlite.py` — factorisation ulterieure (voir **Note 13**)

## Changements realises

Remplacement du PRAGMA, documentation exhaustive du compromis retenu et des
alternatives ecartees directement dans le code.

## Impact

- **Securite** : un verrou anti-force-brute ne peut plus disparaitre a la
  faveur d'un crash, ce qui offrirait un moyen trivial de remise a zero.
- **Performances** : ecritures plus lentes (`fsync`), compensees par le
  regroupement en lots (Note 11).
- **Robustesse** : gain principal — plus de corruption possible sur
  interruption.
- **Gouvernance** : les propositions en attente deviennent durables.

## Compatibilite

Modification purement infrastructurelle. Aucun contact avec le moteur.

## Bonnes pratiques utilisees

- **Choix documente et argumente**, incluant les options ecartees et pourquoi :
  un mainteneur futur ne « corrigera » pas WAL par meconnaissance du contexte.
- **Degradation gracieuse** plutot qu'echec dur.

## Tests effectues

`tests/test_audit.py` verifie explicitement que le mode effectif est bien
`delete` et non `memory` — le test echouerait en cas de retour en arriere.

## Resultat

Les donnees d'audit et de gouvernance resistent desormais a une interruption
brutale, sur un mode de journalisation portable y compris sur partage reseau.

---
---

# Note 03 — Protection contre les attaques par force brute

## Probleme identifie

L'authentification (`auth/utilisateurs.py`) verifiait un couple
identifiant / mot de passe sans **aucune limitation du nombre de tentatives**.
Un adversaire pouvait donc soumettre un nombre illimite de mots de passe.

## Analyse

Le hachage PBKDF2-HMAC-SHA256 a 100 000 iterations impose un cout d'environ
50 ms par essai, ce qui ralentit une attaque mais ne l'empeche pas : les mots
de passe de demonstration (`admin123`) figurent dans tout dictionnaire
d'attaque courant et seraient trouves en quelques secondes.

Deux vulnerabilites connexes ont ete identifiees au cours de l'analyse :

1. **Enumeration par canal temporel** : pour un compte inexistant, la fonction
   retournait immediatement, sans calculer de hash. Le contraste entre une
   reponse instantanee et une reponse a ~50 ms revelait a un observateur
   **quels comptes existent**, sans qu'il ait besoin d'en deviner un seul mot
   de passe.
2. **Comparaison non constante** : l'operateur `!=` sur les hash s'interrompt
   au premier octet different, ce qui fait dependre le temps de reponse de la
   position de la divergence.

**Risques** : compromission d'un compte administrateur, donc acces au
parametrage des regles ; reconnaissance prealable facilitee par l'enumeration.

## Solution retenue

Creation d'un module dedie `auth/tentatives.py` implementant :

| Fonctionnalite | Valeur par defaut | Variable d'environnement |
|---|---|---|
| Tentatives avant verrouillage | 5 | `BIAT_MAX_TENTATIVES` |
| Duree du verrouillage | 15 min | `BIAT_VERROUILLAGE_MINUTES` |

- Verrouillage **par identifiant**, avec **deverrouillage automatique**.
- **Temps restant affiche** a l'utilisateur.
- **Remise a zero** immediate apres une connexion reussie.
- **Journalisation persistante** de chaque tentative echouee.

Un nouveau point d'entree `authentifier()` orchestre l'ensemble. L'API
historique `verifier_identifiants()` est **conservee inchangee** (compatibilite).

## Justification technique

**Pourquoi par compte et non par adresse IP ?**
L'application est destinee a un deploiement interne, derriere un reverse proxy.
L'adresse IP vue par Streamlit y est souvent celle du proxy, donc identique
pour tous les utilisateurs : un verrouillage par IP verrouillerait l'agence
entiere. Le compte est le seul discriminant fiable dans ce contexte. Le revers
— un adversaire peut verrouiller volontairement un compte (deni de service
cible) — est assume et documente.

**Pourquoi verrouiller aussi les comptes inexistants ?**
Contre-intuitif mais essentiel : ne verrouiller que les comptes existants
recreerait le canal d'enumeration que l'on cherche a fermer. Un adversaire
observerait quels identifiants se verrouillent et en deduirait la liste des
comptes valides. Le verrouillage est donc applique **uniformement**, et un
**hash factice** est calcule pour les comptes inconnus afin d'egaliser les
temps de reponse.

**Pourquoi un stockage persistant plutot que `st.session_state` ?**
Un compteur en session serait remis a zero en ouvrant simplement un nouvel
onglet — la protection serait purement decorative.

**Pourquoi `hmac.compare_digest` ?**
Comparaison a temps constant, insensible a la position du premier octet
divergent.

**Pourquoi remettre le compteur a zero a l'expiration du verrou ?**
Sans cela, les echecs de salves successives s'additionneraient et un compte
finirait verrouille en permanence apres quelques erreurs de frappe espacees
dans le temps — une protection qui degraderait l'exploitation legitime.

## Fichiers modifies

- `auth/tentatives.py` (creation)
- `auth/utilisateurs.py` — `authentifier()`, `compare_digest`, hash factice
- `auth/__init__.py` — exposition de la nouvelle API
- `app.py` — branchement du formulaire de connexion
- `.gitignore` — exclusion de `auth/tentatives.sqlite3`
- `tests/test_auth.py` (creation)

## Changements realises

Module de comptage persistant (SQLite), orchestration dans `authentifier()`,
retour structure (`succes`, `verrouille`, `secondes_restantes`,
`tentatives_restantes`, `message`) permettant a l'interface d'afficher un
message precis sans reimplementer la moindre logique.

## Impact

- **Securite** : gain principal. Une attaque par dictionnaire passe de
  quelques secondes a plusieurs annees (5 essais par quart d'heure). Fermeture
  simultanee de deux canaux auxiliaires (enumeration, timing).
- **Performances** : negligeable (une lecture SQLite par tentative).
- **Maintenabilite** : parametres configurables sans modification du code.
- **Robustesse** : compteur persistant, insensible aux reouvertures de session.
- **Experience utilisateur** : messages explicites — nombre d'essais restants,
  puis temps restant avant deverrouillage. Aucun blocage definitif.

## Compatibilite

Le module `auth/` est independant du moteur, dans les deux sens. Aucune
modification de `core/`. `verifier_identifiants()` conserve exactement sa
signature et sa semantique d'origine.

## Bonnes pratiques utilisees

- **Separation des responsabilites** : le comptage (`tentatives.py`) est
  distinct de la verification des identifiants (`utilisateurs.py`).
- **Retrocompatibilite** : ajout d'une API, aucune rupture de l'existante.
- **Configuration externalisee** (variables d'environnement).
- **Securite par defaut** : valeurs prudentes sans configuration.

## Tests effectues

`tests/test_auth.py` — **32 assertions** : comptage progressif, verrouillage au
5e echec, refus meme avec le bon mot de passe, isolation entre comptes,
deverrouillage automatique, remise a zero apres succes, verrouillage des
comptes inexistants, journalisation, configurabilite. Verification
complementaire qu'aucun mot de passe n'apparait en clair dans le fichier de
comptes et que chaque utilisateur possede un sel distinct.

## Resultat

L'authentification resiste aux attaques par force brute et par dictionnaire,
sans jamais bloquer definitivement un utilisateur legitime.

---
---

# Note 04 — Application transactionnelle des changements de regles

## Probleme identifie

L'application d'une proposition de changement de seuils enchainait, directement
dans `app.py`, quatre operations independantes : confirmation de la proposition,
ecriture du fichier de regles, enregistrement de la version, ecriture du journal
d'audit. **Aucun mecanisme ne garantissait leur execution conjointe.**

## Analyse

Chaque etape pouvait echouer isolement (disque plein, fichier verrouille par un
antivirus, arret de l'application), laissant un etat **incoherent** :

- proposition marquee VALIDEE mais regles jamais appliquees ;
- regles appliquees mais aucune version conservee → retour arriere impossible ;
- **regles appliquees mais aucune trace dans le journal d'audit** — soit
  exactement le scenario qu'un controle interne bancaire doit exclure.

Un risque supplementaire concernait l'ecriture elle-meme : `json.dump` ecrivant
directement dans le fichier de regles, une interruption laissait un **JSON
tronque**, rendant l'application entierement inutilisable puisque le moteur ne
pouvait plus charger ses regles.

## Solution retenue

Creation de `gouvernance/application_regles.py`, exposant
`appliquer_proposition()`, qui execute les etapes en empilant pour chacune son
action d'annulation. A la moindre exception, les annulations sont rejouees en
sens inverse et le systeme revient a son **etat initial exact**.

| # | Etape | Annulation |
|---|---|---|
| 1 | Confirmer la proposition | `rouvrir` → EN_ATTENTE |
| 2 | Ecrire les regles (atomique) | restauration a l'octet pres |
| 3 | Enregistrer la version | `supprimer_version` |
| 4 | Ecrire le journal d'audit | **aucune** (append-only) |

## Justification technique

**Pourquoi le journal d'audit en dernier ?**
C'est le point central de la conception. Le journal est **append-only par
construction** : il n'expose aucune fonction de suppression, et lui en ajouter
une pour les besoins du rollback detruirait la propriete meme qui fait sa
valeur (Note 01). C'est donc la seule etape **irreversible**, et toute etape
faillible doit etre tentee **avant** elle. Si le journal echoue, les trois
precedentes sont annulees et l'operation entiere est sans effet : il ne reste
alors **aucune modification a tracer**, donc aucune trace manquante. La
coherence est preservee sans jamais violer l'append-only.

**Pourquoi injecter `enregistrer_audit` en parametre ?**
Application du principe d'**inversion des dependances** (SOLID). Le module de
gouvernance ne depend pas d'une implementation concrete du journal, ce qui (a)
evite un couplage en dur `gouvernance → audit`, et (b) rend le module testable
en injectant une fonction qui echoue a la demande — c'est precisement ainsi que
le rollback est verifie.

**Pourquoi une ecriture atomique (`os.replace`) ?**
`os.replace` est atomique au niveau du systeme de fichiers : le fichier de
regles est soit l'ancien, soit le nouveau, **jamais un etat intermediaire**.

**Pourquoi ne pas exposer `rouvrir` et `supprimer_version` publiquement ?**
Ce sont des primitives de rollback, non des actions metier. Les exposer dans
l'API du paquet laisserait croire qu'effacer une version appliquee ou devalider
une proposition sont des operations legitimes. Du point de vue de
l'utilisateur, l'historique reste strictement append-only. Application du
principe de **ségrégation des interfaces**.

## Fichiers modifies

- `gouvernance/application_regles.py` (creation)
- `gouvernance/workflow_seuils.py` — `rouvrir()`
- `gouvernance/versions.py` — `supprimer_version()`
- `gouvernance/__init__.py` — exposition maitrisee
- `app.py` — remplacement des quatre etapes par un appel unique
- `tests/test_gouvernance.py` (creation)

## Changements realises

Orchestration a pile d'annulations, ecriture atomique du fichier de regles,
protection de chaque annulation (l'echec de l'une n'empeche pas les autres),
distinction entre **refus metier** (auto-confirmation : rien n'a ete touche,
aucun rollback necessaire) et **panne technique** (rollback complet).

## Impact

- **Securite** : impossible d'appliquer un changement de regles sans trace.
- **Performances** : sans objet (operation rare, declenchee manuellement).
- **Maintenabilite** : `app.py` passe de ~25 lignes d'orchestration fragile a
  un appel unique. La logique transactionnelle est testable hors interface.
- **Robustesse** : gain principal — tout ou rien, avec retour a l'etat initial.
- **Gouvernance** : le workflow Maker-Checker ne peut plus produire un etat
  intermediaire ininterpretable.
- **Experience utilisateur** : en cas d'echec, message explicite indiquant
  qu'aucune modification n'a ete appliquee. La proposition reste rejouable.

## Compatibilite

Aucune modification du moteur ni des regles. Le module manipule le **contenu**
du fichier de regles sans jamais l'interpreter : il lui est opaque.

## Bonnes pratiques utilisees

- **Atomicite (ACID)** transposee a un ensemble heterogene (fichier + 2 bases).
- **Pattern Command / pile d'annulations**.
- **Inversion des dependances** (injection de `enregistrer_audit`).
- **Segregation des interfaces** (primitives de rollback non exposees).
- **Ordonnancement par irreversibilite** : l'operation non annulable en dernier.

## Tests effectues

`tests/test_gouvernance.py` — **38 assertions**. Le rollback est verifie en
**injectant une panne a chaque etape faillible** :

- panne du journal d'audit → regles inchangees **a l'octet pres**, proposition
  revenue EN_ATTENTE, `confirme_par` efface, aucune version orpheline, aucun
  fichier temporaire residuel ;
- panne du versionnement → meme resultat ;
- apres rollback, **la meme proposition peut etre rejouee avec succes** — le
  systeme reste pleinement utilisable ;
- refus metier (auto-confirmation) → aucun effet de bord.

## Resultat

L'operation la plus sensible de l'application — la modification de la source
unique de regles — est desormais atomique. Aucune combinaison d'echecs ne peut
produire un etat incoherent.

---
---

# Note 05 — Mise en cache du moteur de segmentation

## Probleme identifie

Streamlit reexecute l'integralite du script a chaque interaction utilisateur
(clic, saisie, changement de page). A chaque rerun, l'application relisait le
fichier de regles, le reparsait et reconstruisait le moteur, le chatbot et
l'assistant — un travail identique repete des dizaines de fois par session.

Par ailleurs, une fonction `charger_regles_cache()` (avec `lru_cache`) existait
dans `core/rules_loader.py` mais **n'etait jamais appelee** : du code mort
temoignant d'une intention non aboutie.

## Analyse

Le surcout unitaire etait modeste mais systematique. Surtout, l'absence de
strategie de cache explicite exposait a un risque plus grave lors d'une
evolution : toute mise en cache naive aurait **fige les regles en memoire**, et
l'application aurait continue de segmenter avec des seuils perimes apres une
modification validee — un defaut silencieux, aux consequences metier directes,
et particulierement difficile a diagnostiquer.

## Solution retenue

Mise en cache via `@st.cache_resource`, avec pour **clef de cache l'empreinte
SHA-256 du contenu** du fichier de regles :

```python
@st.cache_resource(show_spinner=False)
def _construire_moteur(empreinte: str) -> MoteurSegmentation:
    return MoteurSegmentation()

def get_moteur() -> MoteurSegmentation:          # API inchangee
    return _construire_moteur(empreinte_regles())
```

- Regles inchangees → empreinte stable → **une seule instance** reutilisee.
- Regles modifiees → empreinte differente → **reconstruction automatique**.

## Justification technique

**Pourquoi le contenu et non la date de modification (`mtime`) ?**
Un `mtime` presente deux defauts symetriques : (a) deux ecritures dans la meme
seconde peuvent partager le meme horodatage, laissant un **cache perime** — le
scenario dangereux ; (b) une simple recopie modifie le `mtime` sans changer le
contenu, provoquant une **reconstruction inutile**. Le hachage du contenu est
exact dans les deux sens. Son cout (~20 Ko a hacher) est negligeable devant le
parsing JSON et la construction du moteur qu'il evite.

**Pourquoi cette clef plutot qu'un `.clear()` manuel apres modification ?**
Un `.clear()` explicite fonctionnerait, mais reposerait sur la **discipline du
developpeur** : tout nouveau chemin de modification des regles devrait penser a
l'invalider. L'invalidation par empreinte est **structurelle** — elle ne peut
pas etre oubliee, car elle ne demande rien a personne. C'est une application du
principe consistant a rendre les etats incorrects **irrepresentables** plutot
qu'a interdire par convention.

**Reutilisation de l'empreinte comme version des regles**
La meme fonction `empreinte_regles()` identifie la version des regles dans le
journal d'audit. Il n'existe donc qu'**une seule definition** de la notion de
« version des regles » dans toute l'application (DRY), ce qui garantit que la
version tracee dans l'audit et celle qui pilote le cache ne peuvent jamais
diverger.

## Fichiers modifies

- `core/rules_loader.py` — `empreinte_regles()`
- `core/__init__.py` — exposition
- `audit/journal.py` — `_hash_regles_actives()` delegue a `empreinte_regles()`
- `app.py` — fonctions cachees, API `get_moteur()` conservee
- `tests/test_cache.py` (creation)

## Impact

- **Securite** : indirect — l'unicite de la definition de « version des regles »
  garantit que l'audit trace exactement les regles ayant produit la decision.
- **Performances** : suppression de la relecture et du parsing a chaque rerun.
- **Maintenabilite** : suppression du code mort (`charger_regles_cache`) ;
  invalidation impossible a oublier.
- **Robustesse** : impossible de segmenter avec des seuils perimes.
- **Experience utilisateur** : interface plus reactive.

## Compatibilite

`get_moteur()` conserve sa signature. `MoteurSegmentation` reste instanciable
directement et accepte toujours des regles injectees. Aucune ligne du moteur
modifiee.

## Bonnes pratiques utilisees

- **Invalidation par empreinte de contenu** (*content-addressed caching*).
- **DRY** : une seule definition de « version des regles ».
- **Preservation de l'API publique**.
- **Suppression du code mort**.

## Tests effectues

`tests/test_cache.py` — **19 assertions** couvrant les deux garanties
symetriques : **stabilite** (meme empreinte → **exactement la meme instance**,
verifie par identite `is`, avec comptage des constructions) et **invalidation**
(empreinte differente → nouvelle instance ; un seul caractere modifie suffit).
Verification que l'empreinte est **insensible au `mtime`**. Enfin, un test
demontre qu'un seuil modifie change reellement le resultat de segmentation —
etablissant que l'invalidation n'est pas une precaution theorique.

## Resultat

Le moteur est construit une fois et reutilise, avec une invalidation exacte et
automatique. L'API publique est inchangee.

---
---

# Note 06 — Reproductibilite de l'environnement d'execution

## Probleme identifie

`requirements.txt` ne specifiait que des versions **minimales** (`>=`). Deux
installations effectuees a deux dates differentes pouvaient donc produire deux
environnements distincts. Par ailleurs, `numpy` etait importe directement par
`core/ml_anomaly.py` sans etre declare : l'application dependait d'un paquet
qu'elle ne demandait pas, installe par simple transitivite.

## Analyse

Pour une application dont la vocation est d'etre **auditable**, l'impossibilite
de reconstituer a l'identique l'environnement ayant produit une decision est
une faiblesse methodologique. Un risque specifique concerne le modele ML :
`anomaly_pipeline.joblib` est un objet scikit-learn serialise, dont le
rechargement avec une version differente de celle l'ayant produit est
explicitement non supporte.

## Solution retenue

Passage a des versions **exactes** (`==`), relevees sur l'environnement de
reference, et declaration explicite de `numpy`.

## Justification technique

Le figeage garantit qu'une installation ulterieure reproduit l'environnement
valide par les tests. La declaration explicite de `numpy` respecte le principe
selon lequel **une dependance directe doit etre declaree** : s'appuyer sur la
transitivite expose a une rupture silencieuse si `pandas` cessait de dependre
de `numpy`.

**Limite importante identifiee ulterieurement** : figer la version ne suffit pas
si le **modele livre** n'a pas ete produit par la version figee. C'est
precisement le defaut qui s'est revele lors de la revue d'architecture, traite
en **Note 12** — un exemple de justification techniquement correcte mais
factuellement fausse au moment de sa redaction, faute de verification.

## Fichiers modifies

- `requirements.txt`

## Impact

- **Reproductibilite** : gain principal.
- **Robustesse** : protection du modele ML serialise.
- **Maintenabilite** : procedure de montee de version documentee (relancer les
  tests ; reentrainer le modele si scikit-learn change).

## Compatibilite

Aucune modification de code. Les versions figees sont celles sur lesquelles la
non-regression des 715 008 profils a ete etablie.

## Bonnes pratiques utilisees

- **Epinglage des dependances** (*dependency pinning*).
- **Declaration explicite des dependances directes**.
- **Documentation de la procedure de mise a jour**.

## Tests effectues

L'integralite de la suite passe sur l'environnement figé. Un test de garde
verifiant l'accord modele / version a ete ajoute ulterieurement (Note 12).

## Resultat

L'environnement est reproductible a l'identique.

---
---

# Note 07 — Reorganisation et assainissement du depot

## Probleme identifie

Le projet n'etait pas sous gestion de version. Le repertoire contenait, melanges
aux sources : des fichiers d'etat d'execution (`auth/utilisateurs.json`,
contenant les empreintes des mots de passe ; bases `.sqlite3`), des caches
`__pycache__`, un logo `.jpg` inutilise, et un repertoire `competences/` de
fiches documentaires sans lien avec l'application.

## Analyse

L'absence de `.gitignore` faisait courir un **risque de fuite** : une mise sous
version naive aurait publie les empreintes de mots de passe et des donnees
d'exploitation. Le melange sources / etat d'execution nuit par ailleurs a la
lisibilite du projet.

Une verification a etabli que `assets/logo_biat.jpg` etait **effectivement mort**
: `ui/styles.py` sonde les extensions dans l'ordre `png, jpg, ...`, donc le
`.png` l'emporte systematiquement.

## Solution retenue

- `.gitignore` structure et commente, excluant : caches Python, environnements
  virtuels, **etat d'execution** (`auth/utilisateurs.json`, `*.sqlite3`,
  `audit/ancre.json`), fichiers temporaires, fichiers d'IDE, `secrets.toml`.
- Deplacement de `competences/` vers `docs/competences/`.
- Suppression du logo `.jpg` inutilise.
- Section finale du `.gitignore` **enumerant ce qui doit rester versionne**
  (regles, historique des versions, modele ML, logo, donnees de reference).

## Justification technique

**Pourquoi exclure `auth/utilisateurs.json` ?** Il est **regenere
automatiquement** au premier lancement. Le versionner publierait des empreintes
de mots de passe et figerait les comptes de demonstration.

**Pourquoi exclure `audit/ancre.json` ?** L'ancre est indissociable du
`journal.sqlite3` du poste. La versionner ferait echouer le controle
d'integrite sur toute autre installation.

**Pourquoi conserver le modele `.joblib` (2,7 Mo) ?** C'est un artefact livre :
son absence imposerait un reentrainement au premier lancement.

**Pourquoi documenter les inclusions ?** Un `.gitignore` n'enonce que des
exclusions ; la liste explicite des fichiers a conserver previent une exclusion
malencontreuse ulterieure (par exemple `*.json`, qui emporterait les regles).

## Fichiers modifies

- `.gitignore`, `docs/competences/` (deplacement), `assets/logo_biat.jpg`
  (suppression)

## Impact

- **Securite** : plus aucun secret ni etat d'execution versionnable par
  inadvertance.
- **Maintenabilite** : separation nette sources / etat / documentation.

## Compatibilite

Verification explicite qu'apres suppression du `.jpg`, la resolution du logo
retourne toujours le `.png`. Aucun fichier utilise par l'application n'a ete
supprime.

## Bonnes pratiques utilisees

- **Separation code / configuration / etat d'execution**.
- **Aucun secret dans le controle de version**.
- **Documentation des choix d'exclusion et d'inclusion**.

## Tests effectues

Verification que la resolution du logo est inchangee ; controle que les
fichiers sensibles sont bien ignores (`git check-ignore`) ; controle qu'aucun
secret ne figure parmi les fichiers indexes.

## Resultat

Depot propre, sans secret, structure de maniere lisible.

---
---

# Note 08 — Strategie de tests et protocole de non-regression

## Probleme identifie

La couverture de tests se limitait a `tests/test_moteur.py` (31 cas sur le
moteur). Aucun test ne couvrait l'authentification, l'integrite de l'audit, le
workflow de gouvernance ni le cache. Surtout, **aucun protocole ne permettait
de demontrer** que les modifications techniques laissaient les resultats de
segmentation inchanges.

## Analyse

L'engagement central du projet — « les regles metier BIAT restent
inchangees » — ne peut reposer sur une simple affirmation. Les 31 cas existants
verifient des points representatifs, mais ne couvrent qu'une fraction infime de
l'espace des profils : ils ne constituent pas une preuve de non-regression.

## Solution retenue

### 1. Protocole de non-regression exhaustif

Un instantane de reference est produit **avant** toute modification, par
enumeration du produit cartesien :

| Dimension | Valeurs |
|---|---|
| Marches | 6 (dont un non gere et une valeur vide) |
| Professions | 16 (dont vide et hors liste) |
| Ages | 14 (bornes incluses : 0, 18, 19, 30, 31, 120) |
| MMM | 14 (valeurs de seuil et voisines) |
| VRD | 19 (valeurs de seuil et voisines) |
| 8e champ | 2 |

Soit **715 008 profils**. Pour chacun sont enregistres le segment, le
sous-segment, la regle appliquee, le statut, le message **et la trace complete
d'explication**. L'ensemble est condense en une **empreinte SHA-256** unique.

Empreinte de reference, inchangee depuis la v1.0 :

```
19789b8424abaa4310f31128e74a98d624ebafb29015721aaee5d700b14754e8
```

### 2. Extension de la couverture

| Suite | Assertions | Couvre |
|---|---|---|
| `test_moteur.py` | 31 | non-regression metier (inchangee) |
| `test_auth.py` | 32 | hachage, force brute, verrouillage |
| `test_audit.py` | 24 | chainage, ancre, 8 alterations, durabilite |
| `test_gouvernance.py` | 38 | Maker-Checker, transactionnel, rollback |
| `test_cache.py` | 19 | stabilite et invalidation |
| `test_concurrence.py` | 23 | parallelisme, TOCTOU, performances |
| `test_ml.py` | 19 | vectorisation, version, isolation |
| **Total** | **186** | |

Un lanceur unique `tests/run_all.py` execute l'ensemble.

## Justification technique

**Pourquoi inclure les traces d'explication dans l'empreinte ?**
Elles font partie du contrat observable : elles sont affichees au conseiller et
justifient la decision. Une modification qui laisserait les segments identiques
mais altererait les justifications constituerait une regression fonctionnelle.

**Pourquoi les valeurs de seuil ET leurs voisines ?**
Les erreurs de bornes (`>=` vs `>`) sont la premiere source de defauts dans un
moteur de regles. Echantillonner 499 999 / 500 000 / 500 001 autour du seuil
« Fortunes » teste la convention (min inclusif, max exclusif) la ou elle peut
casser.

**Pourquoi inclure des valeurs invalides ?**
Marches inconnus, professions hors liste et champs vides verifient que le
comportement en cas d'echec — message « aucune regle ne correspond » — est lui
aussi preserve.

**Pourquoi ne pas avoir adopte pytest ?**
Decision deliberee. Ajouter pytest introduirait une dependance de test, en
contradiction avec l'objectif de reproductibilite (Note 06) et avec la
contrainte d'installation sur un poste bancaire. Les suites sont donc des
scripts Python natifs partageant un utilitaire commun (`tests/_outils.py`)
offrant compteur, assertions lisibles et **isolation** : chaque suite redirige
les chemins des modules vers un repertoire temporaire et ne touche jamais au
journal, aux comptes ni aux regles reels.

## Fichiers modifies

- `tests/_outils.py`, `tests/run_all.py`, `tests/test_auth.py`,
  `tests/test_audit.py`, `tests/test_gouvernance.py`, `tests/test_cache.py`
  (creations) ; `test_concurrence.py` et `test_ml.py` ajoutes lors de la revue.
- `tests/test_moteur.py` : **volontairement inchange**.

## Impact

- **Qualite** : l'engagement de non-regression devient verifiable.
- **Maintenabilite** : toute evolution future est confrontee au meme protocole.
- **Robustesse** : les mecanismes critiques sont testes par injection de panne
  et par mise en concurrence reelle, non par simple inspection.

## Compatibilite

Le protocole **est** l'instrument de la garantie de compatibilite.

## Bonnes pratiques utilisees

- **Test de caracterisation** (*golden master*) sur un espace exhaustif.
- **Isolation des tests** (aucun effet de bord).
- **Zero dependance de test**.
- **Analyse aux valeurs limites**.

## Tests effectues

7 suites, **186/186 assertions**. Empreinte des 715 008 profils **identique**
avant et apres l'integralite des travaux.

## Resultat

L'affirmation « les regles metier restent inchangees » est etayee par une
preuve reproductible en une commande.

---
---

# Note 09 — Refonte de la documentation technique

## Probleme identifie

Le `README.md` decrivait la v1.0. Aucune documentation n'expliquait les
mecanismes introduits (ancre, transactionnel, cache, force brute), ni surtout
les **raisons** des choix d'architecture.

## Analyse

Une documentation qui enumere des fonctionnalites sans exposer les compromis
retenus laisse le mainteneur suivant sans defense : ignorant pourquoi WAL a ete
ecarte, il l'activera de bonne foi et reintroduira le defaut d'origine.

## Solution retenue

Refonte du `README.md` en sections thematiques (architecture, moteur, audit,
gouvernance, authentification, cache, concurrence, securite, reproductibilite,
tests, organisation), completee par une section **« Limites connues »** et par
la mise a jour du journal d'evolutions de `DOCUMENTATION.md`.

## Justification technique

**Pourquoi documenter les limites ?** Une documentation qui ne mentionne que
les points forts est un argumentaire, pas une documentation. Enoncer que
l'ancre reste locale, ou que le verrouillage par compte autorise un deni de
service cible, permet au lecteur d'evaluer la portee reelle des garanties.

**Pourquoi documenter les alternatives ecartees ?** Le raisonnement a plus de
valeur que la conclusion : il evite qu'une decision correcte soit defaite par
meconnaissance de son contexte.

**Pourquoi documenter dans le code ET dans le README ?** Le README expose
l'architecture d'ensemble ; les commentaires exposent le detail du compromis au
plus pres de l'implementation, la ou il sera lu au moment de la modification.

## Fichiers modifies

- `README.md` (refonte), `DOCUMENTATION.md` (sections 16 et 20),
  `docs/JOURNAL_DEVELOPPEMENT.md` (creation)

## Impact

- **Maintenabilite** : gain principal.
- **Gouvernance** : les garanties et leurs limites sont enoncees explicitement.

## Compatibilite

Sans objet (documentation).

## Bonnes pratiques utilisees

- **Documenter le pourquoi**, pas seulement le quoi.
- **Documentation des limites** et des alternatives ecartees.
- **Documentation au plus pres du code**.

## Tests effectues

Verification que chaque chiffre cite dans le README correspond a une mesure
reelle.

## Resultat

Documentation utilisable comme support de reprise du projet, de redaction du
memoire et de soutenance.

---
---

# Note 10 — Correction des defauts de concurrence

> **Note liminaire.** Les defauts corriges ici ont ete **introduits par la
> version 2.0 elle-meme** et decouverts lors de la revue d'architecture. Ils
> sont consignes sans attenuation : leur analyse constitue le principal
> enseignement d'ingenierie du projet.

## Probleme identifie

Streamlit sert **chaque session utilisateur dans un thread du meme processus**.
Deux conseillers utilisant l'application simultanement executent donc reellement
le meme code en parallele. Aucun mecanisme ne protegeait les acces concurrents.

Quatre defauts, **tous mesures** avant correction :

| # | Defaut | Mesure |
|---|---|---|
| 1 | Ecritures d'audit concurrentes | **19 sur 20 echouent** (`PermissionError`) |
| 2 | Fourche de la chaine de hash | latente, **irreversible** |
| 3 | Compteur d'echecs non deterministe | **10 comptabilises sur 20** |
| 4 | Double validation appliquee deux fois | TOCTOU |

## Analyse

**Defaut 1 — Fichier temporaire partage.** L'ecriture atomique de l'ancre
(Note 01) utilisait un nom de temporaire **fixe** (`ancre.json.tmp`). Sous
Windows, deux threads ouvrant ce meme fichier provoquent un `PermissionError`.
Consequence : **deux conseillers simultanes rendaient l'application
inutilisable**. Le mecanisme cense fiabiliser l'audit avait cree un point de
defaillance.

**Defaut 2 — Fourche de la chaine.** Le cycle « lire le dernier hash → inserer »
n'etait pas atomique. Deux ecrivains simultanes lisaient le meme
`hash_precedent` et produisaient deux entrees referencant le meme parent. La
chaine etait alors **definitivement rompue**, et `verifier_integrite()`
signalerait ensuite une falsification **qui n'a pas eu lieu** — le pire
comportement possible pour un dispositif d'audit : une accusation infondee,
irreversible, contre un utilisateur legitime.

**Defaut 3 — Mises a jour perdues.** Le cycle « lire le compteur → incrementer →
ecrire » s'entrelacait entre threads. Mesure : 20 tentatives paralleles n'en
comptabilisaient que 10. Un compteur de securite dont le resultat depend du
timing n'est pas un compteur de securite.

**Defaut 4 — TOCTOU.** `confirmer()` lisait le statut via `obtenir()` puis
ecrivait dans une transaction distincte. Deux administrateurs confirmant au meme
instant lisaient tous deux `EN_ATTENTE` et validaient la meme proposition,
produisant **deux versions archivees et deux entrees d'audit pour un seul acte
de gouvernance** — une atteinte directe au principe de double validation.

## Solution retenue

**Double protection**, chacune couvrant un cas que l'autre ne couvre pas :

| Mecanisme | Portee | Cas couvert |
|---|---|---|
| `threading.Lock` | threads du processus Streamlit | reel et frequent |
| `BEGIN IMMEDIATE` | processus distincts | 2e instance, script de maintenance |

Appliquee a tout cycle « lire un etat puis l'ecrire » :
`audit/journal.py` (`_ajouter_entrees`), `auth/tentatives.py`
(`enregistrer_echec`), `gouvernance/workflow_seuils.py` (`confirmer`, `rejeter`).

Complements :
- Nom de fichier temporaire **unique par processus et par thread**
  (`ancre.json.<pid>.<tid>.tmp`), avec nettoyage garanti.
- Clause `WHERE ... AND statut='EN_ATTENTE'` avec controle du `rowcount` :
  seconde barriere contre la double validation, efficace **meme sans verrou**.

## Justification technique

**Pourquoi `BEGIN IMMEDIATE` et non le mode transactionnel par defaut ?**
C'est le point technique central. Le module `sqlite3` n'emet un `BEGIN` qu'au
**premier INSERT**, c'est-a-dire **apres** la lecture preparatoire. La fenetre
de course resterait donc grande ouverte : deux transactions liraient le meme
etat avant que l'une d'elles n'acquiere le verrou. `BEGIN IMMEDIATE` prend le
verrou d'ecriture **des l'ouverture**, rendant le cycle lecture-ecriture
reellement indivisible. C'est aussi pourquoi les connexions sont ouvertes avec
`isolation_level=None` : pour reprendre la main sur le pilotage des transactions.

**Pourquoi les deux mecanismes plutot qu'un seul ?**
Le verrou de thread ne franchit pas les frontieres de processus ;
`BEGIN IMMEDIATE` ne protege pas ce qui se passe **hors** de la base (l'ecriture
de l'ancre, qui est un fichier). Ensemble, ils couvrent les deux surfaces. Le
verrou est conserve **pendant** l'ecriture de l'ancre, de sorte que deux
ecrivains ne puissent jamais publier une ancre dans le desordre.

**Pourquoi une clause `WHERE` en plus du verrou ?**
Defense en profondeur : elle rend la double validation impossible au niveau du
SGBD lui-meme, indépendamment de toute erreur applicative future.

**Pourquoi un timeout de 30 s ?**
Sans lui, une connexion trouvant le verrou pris echoue immediatement sur
« database is locked ». Le timeout transforme une erreur en attente.

## Fichiers modifies

- `audit/journal.py` — `_VERROU_ECRITURE`, `_ajouter_entrees`, temporaire unique
- `auth/tentatives.py` — `_VERROU_ECHECS`, transaction indivisible
- `gouvernance/workflow_seuils.py` — `_VERROU_STATUT`, `confirmer`, `rejeter`
- `commun/base_sqlite.py` — `timeout`, `isolation_level=None` (Note 13)
- `tests/test_concurrence.py` (creation)

## Impact

- **Securite** : le compteur anti-force-brute devient exact et deterministe ;
  la separation des taches resiste au parallelisme.
- **Performances** : la serialisation est sans effet mesurable (les sections
  critiques sont breves) ; la refonte a par ailleurs permis l'ecriture par lot
  (Note 11).
- **Maintenabilite** : un point d'ecriture unique dans le journal
  (`_ajouter_entrees`) — une seule implementation du chainage a maintenir.
- **Robustesse** : gain principal — l'application supporte l'usage simultane.
- **Gouvernance** : une proposition ne peut plus etre validee deux fois.
- **Experience utilisateur** : correction d'un defaut **bloquant** — deux
  conseillers simultanes provoquaient des erreurs.

## Compatibilite

Aucune modification du moteur. Empreinte des 715 008 profils inchangee.

## Bonnes pratiques utilisees

- **Verrouillage pessimiste** sur section critique courte.
- **Defense en profondeur** (verrou applicatif + contrainte SQL).
- **Point d'ecriture unique** (DRY sur l'invariant de chainage).
- **Reproduction du defaut avant correction** : chaque defaut a d'abord ete
  **mesure**, puis corrige, puis verrouille par un test.

## Tests effectues

`tests/test_concurrence.py` — **23 assertions**, avec synchronisation par
`threading.Barrier` pour maximiser les collisions :

| Scenario | Avant | Apres |
|---|---|---|
| 20 ecritures d'audit concurrentes | 1/20 | **20/20, chaine intacte** |
| Individuelles + lots melanges | — | 20/20, ancre coherente |
| 20 tentatives paralleles | 10 comptees | **20 comptees, ≤5 testees** |
| 4 confirmations concurrentes | 4 validees | **1 seule** |
| Auto-confirmation en parallele | — | **0 validee** |
| Confirmation vs rejet simultanes | — | **1 seule issue** |

## Resultat

L'application supporte l'usage simultane par plusieurs conseillers, sans perte
d'entree, sans rupture de chaine, sans contournement des controles de securite
ni de gouvernance.

---
---

# Note 11 — Optimisation des traitements en masse

> **Note liminaire.** La regression de performance corrigee ici a ete
> **introduite par la Note 02** : une decision localement correcte
> (`synchronous=FULL`) appliquee sans examiner tous les chemins d'execution.

## Probleme identifie

Deux goulots d'etranglement, mesures sur le chemin d'import CSV :

| Traitement | Mesure |
|---|---|
| Analyse ML d'un import (5 000 lignes) | **73,4 s** |
| Journalisation d'un lot (300 lignes) | **8,31 s** (27,7 ms/ligne) |
| Import complet (5 000 lignes) | **74,4 s** |

Extrapolation : la journalisation d'un import de 5 000 lignes aurait demande
**138 secondes**.

## Analyse

**Goulot 1 — Journalisation ligne par ligne.** `enregistrer_lot()` appelait
`enregistrer()` pour chaque ligne. Chaque appel ouvrait une connexion, relisait
et hachait le fichier de regles, executait un commit avec `fsync`
(`synchronous=FULL`, Note 02) et reecrivait l'ancre avec un second `fsync`. Soit,
pour 5 000 lignes : 5 000 connexions, 5 000 lectures du JSON, 10 000 `fsync`.

Le raisonnement de la Note 02 — « un `fsync` par action utilisateur est
acceptable » — etait juste **pour la simulation individuelle** et faux pour
l'import : une action utilisateur y declenche N ecritures. Le defaut ne vient
pas du choix de `synchronous=FULL`, mais de son application sans examen du
chemin d'execution en masse.

**Goulot 2 — Analyse ML ligne par ligne.** `analyser_dataframe()` iterait via
`df.iterrows()` et appelait `analyser()` par ligne. Chaque appel reconstruisait
un DataFrame d'une seule ligne et invoquait `decision_function` — soit **5 000
invocations scikit-learn distinctes**, dont l'essentiel du cout est un frais
fixe de validation et de transformation. Chaque appel calculait de surcroit des
**explications textuelles aussitot jetees**, le tableau ne renvoyant que
`anomalie`, `confiance` et `niveau`.

**Risque aggravant** : ce cout etait repaye a **chaque interaction Streamlit**
tant que le fichier restait charge. Un conseiller important 5 000 lignes
attendait 74 s, puis 74 s de plus a chaque clic.

## Solution retenue

**Journalisation par lot.** Introduction de `_ajouter_entrees()`, **point
d'ecriture unique** du module, ecrivant N decisions en **une transaction, une
connexion, une lecture du fichier de regles et une ecriture d'ancre**.
`enregistrer()` et `enregistrer_lot()` deviennent de simples adaptateurs.

**Analyse ML vectorisee.** Extraction de `_ligne_modele()` (mise en forme
partagee) et `_scores_bruts()` (un appel unique au modele pour N profils).
`analyser_dataframe()` n'appelle plus `analyser()` et ne calcule plus
d'explications inutiles.

## Justification technique

**Pourquoi la vectorisation est-elle licite ici ?**
Isolation Forest note **chaque ligne independamment des autres** : le score
d'une ligne ne depend pas de la composition du lot. Passer N lignes en un appel
donne donc exactement les memes scores que N appels d'une ligne.

Cette propriete n'a **pas ete supposee mais verifiee** : les scores bruts de
2 000 profils heterogenes ont ete compares **au bit pres** entre les deux
implementations (`np.array_equal` → `True`, ecart maximal **0.0**). Cette
verification etait indispensable : une divergence de dtype entre un DataFrame
d'une ligne et un DataFrame de N lignes aurait pu alterer les resultats de
maniere silencieuse.

**Pourquoi un point d'ecriture unique dans le journal ?**
Au-dela du gain de performance, cela garantit qu'il n'existe qu'**une seule
implementation du chainage de hash et de la mise a jour de l'ancre** — un
invariant a maintenir, pas deux. La correction de concurrence (Note 10) n'a
ainsi eu qu'un seul endroit a proteger.

**Pourquoi une seule lecture du fichier de regles par lot ?**
Toutes les decisions d'un meme lot sont, par construction, prises avec la meme
version des regles. Les relire par ligne etait sans valeur ajoutee.

## Fichiers modifies

- `audit/journal.py` — `_ajouter_entrees`, `_CHAMPS_PROFIL`, refonte de
  `enregistrer` / `enregistrer_lot`
- `core/ml_anomaly.py` — `_ligne_modele`, `_scores_bruts`, `_niveau`,
  vectorisation de `analyser_dataframe`
- `tests/test_ml.py`, `tests/test_concurrence.py`

## Changements realises

| Chemin | Avant | Apres | Facteur |
|---|---|---|---|
| Analyse ML (5 000 lignes) | 73,4 s | 0,18 s | **×400** |
| Import CSV complet (5 000 lignes) | 74,4 s | 1,37 s | **×54** |
| Journalisation d'un lot (300 lignes) | 8,31 s | 0,06 s | **×138** |
| Lectures du JSON de regles | 1 par ligne | 1 par lot | — |

## Impact

- **Securite** : inchangee. La durabilite (`synchronous=FULL`) est **conservee**
  — le gain vient du regroupement, non d'un relachement de la garantie.
- **Performances** : gain principal.
- **Maintenabilite** : un point d'ecriture unique ; suppression du calcul
  d'explications inutiles ; mise en forme des variables ML definie une seule
  fois pour les deux chemins.
- **Robustesse** : le lot est ecrit en tout-ou-rien — un lot partiellement
  ecrit laisserait une chaine coherente mais une ancre fausse.
- **Experience utilisateur** : gain majeur — un import de 5 000 lignes passe de
  74 s a 1,4 s, et chaque interaction ulterieure de 74 s a 1,4 s.

## Compatibilite

- Les API `enregistrer()` et `enregistrer_lot()` conservent leurs signatures.
- Les valeurs ML produites sont **identiques au bit pres** (verifie).
- Empreinte des 715 008 profils **inchangee**.

## Bonnes pratiques utilisees

- **Mesurer avant d'optimiser** : chaque goulot a ete chiffre avant correction.
- **Verifier l'equivalence plutot que la supposer** (comparaison au bit pres).
- **Traitement par lot** (*batching*) plutot que par element.
- **DRY** : point d'ecriture unique, mise en forme unique.
- **Ne pas calculer ce qui sera jete**.

## Tests effectues

- `tests/test_ml.py` : egalite stricte vectorise / ligne-a-ligne sur 500
  profils (`ML_Anomalie`, `ML_Confiance`, `ML_Niveau`) ; scores bruts identiques
  **au bit pres** sur 200 profils.
- `tests/test_concurrence.py` : le fichier de regles est lu **exactement une
  fois** pour un lot de 300 lignes ; duree bornee a 3 s (mesure : 0,04 s ;
  avant correction : 8,31 s) — le test echouerait en cas de retour au regime
  « un `fsync` par ligne ».
- Cas limites ML : DataFrame vide, index non trivial (alignement de la
  concatenation), profil aux champs manquants.

## Resultat

Les traitements en masse sont utilisables en conditions reelles, sans aucune
concession sur la durabilite ni sur l'exactitude des resultats.

---
---

# Note 12 — Coherence entre le modele ML livre et la version figee

> **Note liminaire.** Ce defaut illustre une justification techniquement
> correcte mais **factuellement fausse au moment de sa redaction**, faute de
> verification.

## Probleme identifie

`requirements.txt` figeait `scikit-learn==1.9.0` en justifiant ce choix par la
protection du modele serialise (Note 06). Or le modele livre
(`core/ml_model/anomaly_pipeline.joblib`) avait ete entraine avec
**scikit-learn 1.7.2**. Son chargement declenchait six
`InconsistentVersionWarning` : *« Trying to unpickle estimator [...] from
version 1.7.2 when using version 1.9.0. This might lead to breaking code or
invalid results. »*

## Analyse

Le raisonnement de la Note 06 etait juste dans son principe et faux dans son
application : figer la version ne protege le modele **que si le modele livre a
ete produit par la version figee**. Cette condition n'avait pas ete verifiee.

**Risques** : resultats ML potentiellement invalides selon l'avertissement de
scikit-learn lui-meme ; six avertissements a chaque chargement, nuisant a la
credibilite du projet en soutenance ; **fausse assurance** — la documentation
affirmait une garantie inexistante.

Portee du risque : le module ML est **complementaire** et n'influence jamais la
segmentation (garantie structurelle). L'impact eventuel se limite donc aux
indicateurs de detection d'anomalies. Cela reduit la gravite, sans rendre le
defaut acceptable.

## Solution retenue

Reentrainement du modele avec la version figee (1.9.0), puis **test de garde**
verifiant qu'aucun `InconsistentVersionWarning` n'est emis au chargement.

Correction de la justification de `requirements.txt`, qui enonce desormais la
condition manquante : *figer la version ne suffit pas — encore faut-il que le
modele livre ait ete produit par la version figee*.

## Justification technique

**Pourquoi reentrainer plutot que retrograder scikit-learn a 1.7.2 ?**
Le reentrainement est **deterministe et reproductible** : la generation des
donnees simulees utilise `graine=42` et l'Isolation Forest `random_state=42`.
Le modele est par ailleurs entraine sur des profils **simules** a partir des
ordres de grandeur de la note, non sur des donnees reelles : il n'existe aucune
raison de conserver un artefact historique. Retrograder aurait fige le projet
sur une version anterieure sans aucun benefice.

**Pourquoi un test de garde plutot qu'une simple correction ?**
Le defaut est **silencieux** : rien, hors avertissement, ne le signale. Sans
test, il reapparaitrait a la premiere montee de version de scikit-learn sans
reentrainement. Le test transforme un avertissement ignorable en **echec
franc**, conformement au principe consistant a rendre les defauts silencieux
bruyants.

## Fichiers modifies

- `core/ml_model/anomaly_pipeline.joblib` (reentraine)
- `requirements.txt` — justification corrigee
- `tests/test_ml.py` — test de garde

## Impact

- **Securite** : indirecte — suppression d'un avertissement signalant un risque
  de resultats invalides.
- **Performances** : sans objet.
- **Maintenabilite** : la procedure de montee de version est desormais
  **appliquee par les tests**, non seulement documentee.
- **Robustesse** : le modele livre et l'environnement figé sont garantis
  coherents.
- **Experience utilisateur** : disparition de six avertissements au demarrage.

## Compatibilite

Le module ML est structurellement independant du moteur : `core/ml_anomaly.py`
n'importe jamais `core/engine.py`, et reciproquement. Le reentrainement ne peut
donc affecter aucun segment. Empreinte des 715 008 profils **inchangee**,
verifiee apres reentrainement.

## Bonnes pratiques utilisees

- **Verifier ses propres affirmations** plutot que les supposer.
- **Rendre bruyant un defaut silencieux** (test de garde).
- **Reproductibilite par graine fixe**.
- **Correction de la documentation fautive**, et non seulement du code.

## Tests effectues

`tests/test_ml.py` charge le modele en capturant les avertissements et echoue si
un `InconsistentVersionWarning` apparait. Verification complementaire en mode
`warnings.simplefilter('error')` : chargement propre. Empreinte de
non-regression du moteur controlee apres reentrainement.

## Resultat

Le modele livre, la version figee et la documentation sont mutuellement
coherents, et cette coherence est verrouillee par un test.

---
---

# Note 13 — Factorisation du socle d'acces aux donnees (DRY)

## Probleme identifie

Trois modules ouvraient une base SQLite — `audit/journal.py`,
`auth/tentatives.py`, `gouvernance/workflow_seuils.py` — en repetant chacun le
meme bloc de configuration (PRAGMA, timeout, pilotage des transactions).

La revue a etabli que **les copies avaient diverge** :
`gouvernance/workflow_seuils.py` etait reste en `journal_mode=MEMORY`, sans
`timeout` ni `isolation_level`, alors que les deux autres avaient ete durcis
(Note 02).

## Analyse

Ce defaut est la **manifestation exacte du risque que la duplication fait
courir** : lors du durcissement, deux copies sur trois ont ete mises a jour et
la troisieme oubliee. Aucun mecanisme ne pouvait le signaler, chaque copie etant
syntaxiquement valide.

**Consequences concretes** :
- les **propositions de changement de regles en attente n'etaient pas
  durables** : une coupure pouvait corrompre la base de gouvernance ;
- l'absence de `timeout` faisait echouer toute ecriture concurrente sur
  « database is locked » ;
- l'absence d'`isolation_level=None` empechait le pilotage explicite des
  transactions, indispensable a la correction TOCTOU (Note 10).

Le module de gouvernance est celui qui porte le **controle Maker-Checker**,
c'est-a-dire le mecanisme de gouvernance le plus sensible de l'application.

## Solution retenue

Creation du paquet `commun/`, contenant `base_sqlite.py` et exposant
`connexion_durable(chemin)` : **definition unique** de la configuration
(`journal_mode=DELETE`, `synchronous=FULL`, `timeout=30 s`,
`isolation_level=None`, repli sur `MEMORY`).

Les trois modules delegent desormais leur ouverture de connexion a cette
fonction. La documentation exhaustive des compromis (pourquoi pas WAL, cout du
`fsync`, role d'`isolation_level`) reside en un seul endroit.

## Justification technique

**Pourquoi un paquet dedie plutot qu'un module utilitaire dans `core/` ?**
Question d'architecture. `core/` est le **domaine metier** : il contient le
moteur et les regles. Y placer un utilitaire d'infrastructure melangerait deux
niveaux d'abstraction et creerait une dependance `audit → core` non justifiee
par le metier. `commun/` est un **socle technique** explicitement dépourvu de
toute connaissance metier — aucun seuil, aucun segment, aucune regle — ce qui
le rend importable par toutes les couches **sans jamais creer de dependance
vers le metier**. Cette contrainte est enoncee dans la docstring du paquet.

**Pourquoi ne pas avoir simplement corrige la troisieme copie ?**
Cela aurait retabli l'etat correct sans traiter la cause. Une quatrieme base
serait apparue, avec une quatrieme copie a maintenir, et la divergence se
reproduirait a la prochaine evolution. Factoriser rend l'oubli **structurellement
impossible** : il n'existe plus qu'un seul endroit a modifier.

**Pourquoi laisser aux appelants la gestion des transactions ?**
Separation des responsabilites : `connexion_durable` a une responsabilite unique
— ouvrir une connexion correctement configuree. Les invariants transactionnels
(`BEGIN IMMEDIATE`) relevent de la logique propre a chaque module, qui seul sait
quel cycle doit etre indivisible. Y placer une politique transactionnelle
imposerait un choix inadapte a certains appelants (SRP).

## Fichiers modifies

- `commun/__init__.py`, `commun/base_sqlite.py` (creations)
- `audit/journal.py`, `auth/tentatives.py`, `gouvernance/workflow_seuils.py`
  (delegation)

## Impact

- **Securite** : la base de gouvernance beneficie enfin de la durabilite.
- **Performances** : sans effet mesurable.
- **Maintenabilite** : gain principal — une seule regle a faire evoluer ; la
  divergence silencieuse devient impossible.
- **Robustesse** : les propositions en attente sont durables ; les ecritures
  concurrentes attendent le verrou au lieu d'echouer.
- **Gouvernance** : le module portant le controle Maker-Checker cesse d'etre le
  maillon faible.

## Compatibilite

`commun/` ne contient aucune logique metier. Aucune modification du moteur.
Empreinte des 715 008 profils inchangee.

## Bonnes pratiques utilisees

- **DRY** — appliqué a la cause, non au symptome.
- **Principe de responsabilite unique (SRP)** : ouvrir une connexion ≠ piloter
  une transaction.
- **Clean Architecture** : socle technique sans dependance vers le metier ; les
  dependances pointent de l'infrastructure vers le domaine, jamais l'inverse.
- **Documentation centralisee** du compromis, au plus pres de la decision.

## Tests effectues

Verification par recherche exhaustive qu'il n'existe plus qu'**une seule**
occurrence de `sqlite3.connect` et de configuration PRAGMA dans tout le code de
production. `tests/test_audit.py` verifie que le mode effectif est bien `delete`.
Les 7 suites (186 assertions) passent apres refactorisation.

## Resultat

Une definition unique de la configuration d'acces aux donnees, appliquee
uniformement aux trois bases. La cause de la divergence est eliminee, non
seulement son symptome.

---
---

## Synthese de la version 2.0

### Bilan quantitatif

| Indicateur | v1.0 | v2.0 |
|---|---|---|
| Suites de tests | 1 | **7** |
| Assertions | 31 | **186** |
| Familles d'alteration d'audit detectees | 3 sur 5 | **5 sur 5** |
| Ecritures concurrentes reussies (sur 20) | 1 | **20** |
| Import CSV de 5 000 lignes | 74,4 s | **1,37 s** |
| Analyse ML de 5 000 lignes | 73,4 s | **0,18 s** |
| Definitions de la configuration SQLite | 3 (divergentes) | **1** |
| Dependances figees | non | **oui** |
| **Empreinte des 715 008 profils** | `19789b84…54e8` | **`19789b84…54e8`** |

### Enseignements d'ingenierie

1. **Une amelioration non mesuree peut etre une regression.** `synchronous=FULL`
   (Note 02) etait un progres pour la simulation individuelle et une regression
   de 17× pour l'import en masse. Seule la mesure a permis de le savoir.
2. **La duplication ne fait pas courir un risque theorique.** Trois copies de la
   configuration SQLite ont bel et bien diverge, et c'est la plus sensible qui
   a ete oubliee (Note 13).
3. **Une justification n'est pas une verification.** L'epinglage de scikit-learn
   etait documente comme protegeant le modele ; il ne le protegeait pas
   (Note 12).
4. **La concurrence n'est pas un sujet theorique** des lors que le framework
   sert chaque session dans un thread (Note 10).
5. **Un dispositif de securite peut creer le defaut qu'il pretend prevenir** :
   l'ecriture atomique de l'ancre rendait l'application inutilisable a deux
   utilisateurs simultanes (Note 10, defaut 1).
6. **La valeur d'un test tient a ce qu'il verrouille.** Chaque test ajoute lors
   de la revue correspond a un defaut **reellement constate et mesure**.

### Limites connues et perspectives

| Limite | Perspective |
|---|---|
| Ancre d'integrite locale | temoin hors serveur : replication, horodatage tiers, stockage WORM |
| Comptes locaux | federation d'identite (OIDC/SAML sur l'AD), MFA pour admin/auditeur |
| SQLite mono-instance | SGBD serveur (PostgreSQL) pour un deploiement multi-serveurs |
| Verrouillage par compte | analyse de risque sur le deni de service cible |
| `verifier_integrite()` charge tout le journal | lecture par blocs au-dela de ~100 000 entrees |
| Re-segmentation a chaque rerun (~1,4 s / 5 000 lignes) | `@st.cache_data` sur le contenu du fichier |
| Portee de l'ancre | ne couvre le tronquage qu'a partir de son initialisation |

---
---

# Note 14 — Fiabilisation du chatbot expert : recherche et source unique

> **Origine** : defaut signale par l'utilisateur en usage reel, sur une capture
> d'ecran de l'application. L'investigation a revele **trois defauts distincts**,
> dont deux preexistants a la version 2.0.

## Probleme identifie

A la question « quand je modifier le mmm ca change quoi ? », le chatbot
repondait correctement sur la logique MMM/VRD, puis enchainait sur un
paragraphe consacre a la **residence et a la reglementation de change**, sans
aucun rapport avec la question posee.

L'analyse a mis au jour trois defauts cumules :

| # | Defaut | Gravite |
|---|---|---|
| 1 | Recherche par sous-chaine : faux positifs massifs | Elevee |
| 2 | Empilement systematique des deux meilleures reponses | Moyenne |
| 3 | **Seuils ecrits en dur, contredisant le moteur** | **Critique** |

## Analyse

### Defaut 1 — Recherche par sous-chaine

La selection s'ecrivait :

```python
score = sum(1 for cle in entree["cles"] if _norm(cle) in q)
```

Le test `in` est une recherche de **sous-chaine** : un mot-cle etait reconnu des
qu'il apparaissait **a l'interieur d'un autre mot**. Correspondances reellement
observees :

| Cle | Reconnue dans | Consequence |
|---|---|---|
| `and` | qu**and** | l'entree MMM gagnait un point parasite |
| `change` | ca **change** quoi | l'entree Residence etait activee |
| `ou` | p**ou**vez, p**ou**r | preposition la plus courante du francais |
| `pl` | ex**pl**iquer, exem**pl**e | tres frequent |
| `tre` | au**tre**, no**tre**, e**tre** | omnipresent |

La quasi-totalite des questions en langage naturel declenchait ainsi au moins
une correspondance parasite. Dans le cas signale, l'entree MMM/VRD obtenait
2 points (`mmm` + `and` dans « quand ») et l'entree Residence 1 point
(`change` dans « ca change quoi »).

### Defaut 2 — Empilement inconditionnel

Le code renvoyait **systematiquement les deux meilleures** entrees, quel que
soit leur ecart de score : une entree ayant obtenu 1 point par un mot-cle
marginal etait presentee au meme rang qu'une entree en ayant obtenu 2
pertinents. L'utilisateur recevait une reponse juste suivie d'une reponse hors
sujet, **sans moyen de distinguer laquelle repondait a sa question**.

### Defaut 3 — Seconde copie des regles

L'investigation a revele un defaut plus grave, sans rapport avec la question
initiale : **les seuils cites par le chatbot etaient ecrits en dur** dans le
texte des reponses. Ils constituaient donc une **seconde copie des regles**, en
contradiction directe avec le principe fondateur du projet
(`config/regles_segmentation.json` = source unique).

Ce defaut ne relevait pas de l'hypothese : **il s'etait deja materialise**. La
correction des seuils MMM du marche TRE — documentee dans
`_notes_conflits.tre_mmm_vs_revenu_CORRIGE` (la colonne « Revenus » du tableau
de la note avait ete confondue avec la colonne « MMM ») — avait ete appliquee
au fichier de regles le 2026-07-07 **mais pas au texte du chatbot** :

| Marche TRE | Chatbot annoncait | Moteur appliquait |
|---|---|---|
| Premium, MMM | **>= 10 mD** | **>= 2,5 mD** |
| Potentiel moyen, MMM | **>= 5 mD** | **>= 1 mD** |
| Faible potentiel, MMM | **< 5 mD** | **< 1 mD** |

Le chatbot annoncait donc aux conseillers des seuils que le moteur
n'appliquait plus. Une verification complementaire a montre que le meme
mecanisme rendait le chatbot **incapable de suivre une modification validee en
page Parametrage** : apres un relevement du seuil Fortunes a 600 mD, le moteur
classait correctement un client a 550 mD en « Grand Public » tandis que le
chatbot continuait d'affirmer « VRD >= 500 mD ».

**Risques** : un conseiller s'appuyant sur le chatbot pour justifier une
decision aupres d'un client transmettait une information erronee ; l'outil cense
faire autorite sur la note la contredisait ; et toute evolution future des
seuils aurait aggrave l'ecart.

## Solution retenue

1. **Recherche par mot entier** : fonction `_contient_mot()` s'appuyant sur les
   bornes de mot (`\b`) plutot que sur le test `in`.
2. **Mots-cles assainis** : retrait de `ou`, `and`, `or` (operateurs logiques
   inexploitables comme mots-cles) ; `change` remplace par la locution complete
   `reglementation de change`.
3. **Seuils derives de la source unique** : methodes `_seuil()`, `_plage()` et
   `_age_min()` lisant les valeurs dans les regles du moteur. Les listes de
   professions etaient deja construites ainsi ; le principe est simplement
   etendu aux valeurs numeriques.
4. **Selection par score** : seules les entrees **aussi pertinentes que la
   meilleure** sont renvoyees.

## Justification technique

**Pourquoi ne pas tolerer automatiquement les pluriels (`\bcle s?\b`) ?**
Cela ferait correspondre la cle `tre` (marche TRE) au mot tres frequent
« tres ». La base de connaissances declare deja explicitement les variantes
utiles (`marche`/`marches`, `liberale`/`liberales`), rendant la tolerance
inutile et dangereuse.

**Pourquoi retirer `ou` plutot que le traiter specialement ?**
Un operateur logique n'a aucune valeur discriminante comme mot-cle. L'entree
reste atteinte par `mmm`, `vrd`, `combinaison` et `logique` : une question du
type « MMM ou VRD ? » continue d'y repondre (verifie par test).

**Pourquoi deriver les seuils plutot que corriger les valeurs erronees ?**
Corriger les nombres aurait retabli l'exactitude **du jour**, sans traiter la
cause : la duplication. La divergence se serait reproduite a la modification
suivante. Deriver les valeurs rend l'incoherence **structurellement
impossible** — c'est le meme raisonnement que pour la factorisation du socle
SQLite (Note 13) : traiter la cause, non le symptome.

**Le contenu metier est-il modifie ?**
Non, et c'est un point essentiel. Les **libelles** des reponses restent ceux de
la note ; seules les **valeurs** sont desormais lues dans le fichier de regles,
lui-meme issu exclusivement de la note. Le chatbot cesse de detenir une opinion
propre sur les seuils : il **rapporte** ceux du moteur. Les corrections
observees (TRE 2,5 mD au lieu de 10 mD) ne sont pas des modifications de regle,
mais l'alignement du chatbot sur la regle **deja en vigueur** dans le moteur.

**Pourquoi `_age_min()` renvoie-t-elle la borne moins un ?**
La regle porte `age >= 31` ; la note dit « plus de 30 ans ». La methode preserve
la formulation d'origine tout en derivant la valeur de la source unique : la
fidelite redactionnelle n'impose pas de dupliquer la donnee.

## Fichiers modifies

- `chatbot/expert.py` — `_contient_mot`, `_seuil`, `_plage`, `_age_min`,
  mots-cles assainis, selection par score
- `tests/test_chatbot.py` (creation)
- `tests/run_all.py` — integration de la suite

## Changements realises

- Recherche par bornes de mot au lieu de sous-chaine.
- Neuf entrees de la base de connaissances derivent desormais leurs seuils des
  regles (Fortunes, Patrimoniaux, Affluent, Professionnels, Classe Moyenne,
  Grand Public, Les Jeunes, TRE, ENR).
- Selection limitee aux entrees a score maximal.

## Impact

- **Securite** : sans objet direct.
- **Performances** : negligeable (une expression reguliere par mot-cle).
- **Maintenabilite** : suppression de la seconde copie des seuils ; une
  modification de regle n'exige plus aucune intervention sur le chatbot.
- **Robustesse** : le chatbot ne peut plus contredire le moteur.
- **Gouvernance** : gain majeur — une modification validee en Parametrage
  (double validation) est immediatement refletee dans les reponses du chatbot.
  Le principe de **source unique** est enfin respecte par ce module.
- **Experience utilisateur** : gain majeur — les reponses cessent d'etre
  polluees par des paragraphes hors sujet, et surtout **cessent d'annoncer des
  seuils faux**.

## Compatibilite

- **Aucune modification du moteur** : `core/engine.py` n'est pas touche.
- **Aucune regle metier modifiee** : le chatbot rapporte desormais les regles
  du JSON au lieu d'une copie perimee. Les valeurs affichees changent
  (TRE : 2,5 mD au lieu de 10 mD) parce que la copie etait fausse, non parce
  que la regle a change.
- Empreinte des 715 008 profils **inchangee** : `19789b84...54e8`.

## Bonnes pratiques utilisees

- **Source unique de verite (Single Source of Truth)** appliquee jusqu'au bout.
- **DRY** : traiter la cause (la duplication), non le symptome (les valeurs).
- **Correspondance par mot entier** plutot que par sous-chaine.
- **Reproduction du defaut avant correction**, puis verrouillage par test.

## Tests effectues

`tests/test_chatbot.py` — **49 assertions** :

- la question de l'utilisateur ne declenche plus la reponse sur la residence ;
- neuf correspondances internes verifiees comme supprimees (`and` dans
  « quand », `tre` dans « autre », `pl` dans « expliquer »...) ;
- les memes cles restent reconnues comme **mots entiers** (`TRE`, `ENR`, `PL`,
  `500`) — la correction ne degrade pas la recherche legitime ;
- les huit exemples de questions de l'interface donnent toujours la bonne
  reponse (non-regression) ;
- **TRE annonce 2,5 mD et 1 mD**, et plus les valeurs erronees ;
- **test decisif** : un seuil porte a 600 mD est immediatement reflete dans la
  reponse, et l'ancienne valeur disparait — la divergence ne peut pas revenir ;
- le chatbot delegue au moteur (segment, sous-segment et regle identiques a un
  appel direct) ;
- les questions hors sujet renvoient toujours le message d'absence : le chatbot
  n'invente jamais.

**Anecdote methodologique.** La premiere version de ce test verifiait l'absence
des valeurs erronees par `"5 mD" not in reponse`, et echouait — car `"5 mD"` est
une sous-chaine de `"25 mD"`. Le test reproduisait donc **exactement le defaut
qu'il devait verrouiller**. Meme une borne de mot n'y suffisait pas : dans
`"2.5 mD"`, le point cree une borne juste avant le `5`. L'assertion finale porte
sur les locutions exactes (`"MMM >= 10 mD"`), ce qui exprime sans ambiguite ce
qui est verifie. Cet episode illustre concretement pourquoi le defaut d'origine
etait facile a commettre et difficile a voir : la comparaison de chaines sans
notion de mot est une source d'erreur qui resiste meme a l'attention de celui
qui vient de la corriger ailleurs.

## Resultat

Le chatbot repond a la question posee, sans paragraphe parasite, et **rapporte
desormais les seuils reellement appliques par le moteur**. Trois seuils TRE
faux, presents depuis la correction du 2026-07-07, ont ete elimines — non par
une correction ponctuelle, mais en supprimant la duplication qui les avait
rendus possibles.

---

*Les notes sont ajoutees a la suite, sans jamais modifier ni supprimer les
precedentes. La synthese de la version 2.0 ci-dessus reste l'etat a la
cloture de cette version ; les notes posterieures la completent.*
