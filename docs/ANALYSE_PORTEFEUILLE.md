# Analyse de la structure du portefeuille client PBD

> Rapport genere automatiquement le 2026-07-24 par `python -m analyse_portefeuille.rapport`.

## Question metier

**Comment se structure le portefeuille de la clientele PBD, ou se concentre la valeur, et quels leviers commerciaux en decoulent ?**

## Avertissement sur les donnees

En l'absence de donnees clients reelles BIAT, l'analyse porte sur un **portefeuille representatif simule** de 8000 clients (graine fixee = 1234, reproductible), **segmente par le moteur officiel**. Les profils sont simules ; les **segments sont reels** (produits par le moteur applique a la Note BIAT 2023-06). Les hypotheses de generation (mix de marche, professions, montants) sont explicites dans le code (`analyse_portefeuille/portefeuille.py`). Ces chiffres illustrent une METHODE d'analyse ; ils devront etre rejoues sur donnees reelles.

Mix de marche suppose : PART 68 %, PRO 18 %, TRE 9 %, ENR 5 %.

## 1. Repartition par segment

| Segment | Part du portefeuille |
|---|---|
| Grand Public | 30,6 % |
| Classe Moyenne | 24,9 % |
| Les Jeunes | 22,7 % |
| Faible potentiel | 11,7 % |
| Haut de Gamme | 7,8 % |
| Potentiel moyen | 1,4 % |
| Premium | 0,9 % |

Lecture : le portefeuille forme une **pyramide** classique -- une base large de clientele de masse (Grand Public / Faible potentiel : 42,3 %), une classe intermediaire, et un sommet etroit de forte valeur (Haut de Gamme / Premium : 8,7 %).

## 2. Concentration des avoirs

- Le **decile superieur** des clients detient **41,8 %** des avoirs totaux ; le **top 20 %** en detient **58,8 %**.
- **Indice de Gini** des avoirs : **0,548** (0 = egalite parfaite, 1 = concentration maximale).
- Nuance : les segments de valeur (Haut de Gamme / Premium, 8,7 % des clients) ne detiennent que 12,1 % des avoirs, car une partie de ces clients sont qualifies par leur **profession** (a potentiel) et non par leurs montants. La valeur commerciale (relation) et la valeur patrimoniale (encours) ne se recouvrent donc pas totalement -- distinction utile au pilotage.

## 3. Croisement marche x segment

| Marche | Classe Moyenne | Faible potentiel | Grand Public | Haut de Gamme | Les Jeunes | Potentiel moyen | Premium |
|---|---|---|---|---|---|---|---|
| ENR | 0 % | 94 % | 0 % | 0 % | 0 % | 5 % | 1 % |
| PART | 30 % | 0 % | 29 % | 7 % | 33 % | 0 % | 0 % |
| PRO | 23 % | 0 % | 61 % | 16 % | 0 % | 0 % | 0 % |
| TRE | 0 % | 78 % | 0 % | 0 % | 0 % | 13 % | 9 % |

Par marche : **ENR** (400 clients) : dominante Faible potentiel (94,5 %), valeur 0,8 % ; **PART** (5440 clients) : dominante Les Jeunes (33,3 %), valeur 7,4 % ; **PRO** (1440 clients) : dominante Grand Public (61,2 %), valeur 15,6 % ; **TRE** (720 clients) : dominante Faible potentiel (77,8 %), valeur 9,3 %.

## 4. Qualite des donnees (module ML)

Le module de detection d'anomalies signale **11,4 %** de profils atypiques dans ce portefeuille -- indicateur de la part de saisies potentiellement incoherentes a controler (voir `docs/EVALUATION_ML.md` pour l'evaluation du modele).

## 5. Constats

- Le portefeuille compte 8000 clients, dont 68.0 % sur le marche des Particuliers.
- Les avoirs sont fortement concentres : le decile superieur des clients detient 41.8 % des encours (top 20 % : 58.8 %), pour un indice de Gini de 0.548.
- La clientele de forte valeur au sens des segments (Haut de Gamme / Premium) represente 8.7 % des clients et detient 12.1 % des avoirs -- ecart avec le decile superieur qui s'explique par les clients qualifies par la profession (a potentiel) plutot que par les montants.
- Le marche de masse (Grand Public / Faible potentiel) represente 42.3 % des clients.
- Les Jeunes representent 22.7 % du portefeuille (potentiel de developpement futur).
- Le marche PRO est le plus riche en clientele de valeur (15.6 % de Haut de Gamme / Premium).

## 6. Recommandations

Recommandations derivees des indicateurs ci-dessus (chaque point est declenche par un chiffre du portefeuille, non pose a priori) :

1. Forte concentration des avoirs (le decile superieur detient 41.8 % des encours, Gini 0.548) : la priorite est de securiser et fideliser cette clientele patrimoniale par une gestion dediee, sa perte ayant un impact disproportionne sur les encours.
2. Marche de masse important (42.3 %) : levier de montee en gamme via des produits d'epargne et de bancarisation, pour faire progresser une partie de ces clients vers la Classe Moyenne.
3. Les Jeunes representent 22.7 % : une strategie de fidelisation precoce (offres d'equipement, accompagnement) permettrait de les convertir en clients Affluent a mesure de la hausse de leurs revenus.
4. Marches TRE/ENR majoritairement en faible potentiel (ENR 94.5 %, TRE 77.8 % de faible potentiel) : clientele expatriee aux encours modestes. Opportunite de developpement (produits de transfert, epargne rapatriee) ou choix assume de ne pas y investir -- a arbitrer.
5. Le module de detection signale 11.4 % de profils atypiques : un controle qualite des donnees d'entree (saisies incoherentes) fiabiliserait la segmentation et les analyses qui en decoulent.

## 7. Limites et suite

- **Donnees simulees** : a rejouer sur historique client reel des qu'il sera disponible ; les valeurs changeraient, la methode non.
- **Hypotheses de generation** explicites et discutables (mix de marche, professions) : elles conditionnent les chiffres, pas la demarche.
- L'analyse est **reproductible** (`python -m analyse_portefeuille.rapport`) et **verrouillee** par `tests/test_analyse_portefeuille.py`.
