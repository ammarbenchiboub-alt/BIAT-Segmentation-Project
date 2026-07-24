# Evaluation du modele de detection d'anomalies (Isolation Forest)

> Rapport genere automatiquement le 2026-07-24 par `python -m evaluation.rapport`.
> Chiffres issus directement des mesures (`evaluation.mesures.evaluer`), sur le modele livre.

## 1. Objet

Ce rapport evalue rigoureusement le module de detection d'anomalies (Isolation Forest), afin de justifier son emploi. Le modele **n'est pas modifie** : il est charge tel quel et note sur un jeu de reference etiquete. Le module de detection reste **complementaire** au moteur de segmentation, qu'il ne remplace ni ne modifie jamais.

## 2. Methodologie

Le modele est non supervise et entraine sur des donnees **simulees** : il n'existe donc aucune anomalie de reference « naturelle ». On construit un jeu d'evaluation **etiquete** et reproductible :

- **2000 profils normaux** tenus a l'ecart : meme distribution que l'entrainement mais **graine differente** (aucune fuite) ;
- **600 anomalies injectees**, etiquetees par type, chacune representant une erreur de saisie ou une combinaison implausible.

Familles d'anomalies :

- **montant_extreme** : Montants MMM/VRD hors de toute echelle realiste (erreur de saisie de grande ampleur).
- **age_enfant_marche_adulte** : Age d'enfant (6-15 ans) sur un marche reserve aux adultes (PRO/TRE/ENR).
- **etudiant_age_incoherent** : Profession 'Etudiant' associee a un age eleve (45-70 ans).
- **ENR_nationalite_tunisienne** : Marche ENR (Etranger Non Resident) avec Nationalite = Tunisienne (contradiction).
- **TRE_resident_oui** : Marche TRE (Resident a l'Etranger) avec Residence = Oui (contradiction).

> Limite methodologique assumee : l'evaluation mesure la capacite du modele a retrouver des anomalies **connues et injectees**, selon la definition ci-dessus. Les donnees d'entrainement etant simulees, les resultats sont conditionnels a ces hypotheses. C'est la demarche standard en detection non supervisee faute de labels reels.

## 3. Resultats globaux

| Metrique | Isolation Forest | Baseline (regles simples) |
|---|---|---|
| ROC-AUC (classement) | **0,931** | 0,770 |
| PR-AUC | 0,759 | 0,647 |
| Precision (au seuil) | 0,703 | 0,432 |
| Rappel (au seuil) | 0,438 | 0,700 |
| F1 (au seuil) | 0,540 | 0,534 |
| **Fausses alertes sur clients normaux** | **5,5 %** | 27,6 % |

La baseline est un detecteur transparent (z-score robuste par marche sur MMM/VRD + bornes d'age), representant « ce qu'on obtiendrait avec quelques regles simples ».

### Lecture

- **Discrimination** : l'Isolation Forest classe nettement mieux les anomalies (ROC-AUC 0,931 contre 0,770 pour la baseline).
- **Fausses alertes, le point decisif** : au seuil de production, la baseline signale **27,6 %** des clients NORMAUX a tort — inexploitable en agence. L'Isolation Forest se limite a **5,5 %**. La baseline n'atteint son rappel eleve qu'au prix d'un deluge de fausses alertes.
- **Rappel modere (0,438) au seuil actuel** : le modele est volontairement conservateur (peu de fausses alertes). La courbe operationnelle (section 5) montre qu'on peut le rendre plus sensible si on accepte davantage de fausses alertes.

## 4. Interpretation de `contamination = 0.06`

Mesure : le modele signale **5,5 %** des profils normaux — soit tres exactement l'ordre de grandeur de `contamination = 0.06`. Ce parametre n'est donc **pas arbitraire** : il fixe le **budget de fausses alertes** accepte sur la clientele normale (~6 %). Le retenir a 6 % est un choix operationnel (volume d'alertes soutenable pour un conseiller), desormais **mesure et justifie**, et non plus un nombre pose sans raison.

## 5. Courbe operationnelle (justification du seuil)

Pour differents budgets de fausses alertes (seuil fixe sur la distribution des scores des clients normaux), rappel obtenu sur les anomalies :

| Budget de fausses alertes | Rappel des anomalies |
|---|---|
| 2,0 % | 0,223 |
| 4,0 % | 0,355 |
| 6,0 % *(reglage actuel)* | 0,545 |
| 8,0 % | 0,710 |
| 10,0 % | 0,747 |
| 15,0 % | 0,855 |

Lecture : augmenter le budget accroit le rappel, au prix de plus de fausses alertes. Le reglage a 6 % privilegie la sobriete des alertes ; un reglage plus eleve serait justifiable si l'on souhaitait detecter davantage d'anomalies. Ce compromis est desormais **explicite et quantifie**.

## 6. Forces et faiblesses par type d'anomalie

| Type d'anomalie | Rappel Isolation Forest | Rappel Baseline |
|---|---|---|
| montant_extreme | 100,0 % | 100,0 % |
| age_enfant_marche_adulte | 48,3 % | 100,0 % |
| etudiant_age_incoherent | 35,8 % | 100,0 % |
| ENR_nationalite_tunisienne | 6,7 % | 24,2 % |
| TRE_resident_oui | 28,3 % | 25,8 % |

- **Montants extremes** : parfaitement detectes par les deux methodes.
- **Age / profession incoherents** : bien captes par une regle d'age explicite (baseline) ; le modele, plus conservateur, en detecte une partie seulement.
- **Incoherence purement categorielle** (nationalite / residence contradictoires, montants normaux) : **faiblesse commune**. Un seul champ categoriel errone parmi sept se dilue dans le score d'isolement. Ni le modele ni des regles de montant ne traitent bien ce cas.

## 7. Le modele apporte-t-il une valeur reelle vs les regles ?

**Oui, une valeur mesurable, mais ciblee — pas un remplacement des regles.**

- Le moteur de segmentation **classe** ; il ne detecte pas les saisies incoherentes (il segmenterait sans broncher un client de 10 ans sur PRO). Le modele fournit ce filet de securite.
- Face a une baseline naive, l'Isolation Forest apporte un gain **decisif sur le controle des fausses alertes** (5,5 % contre 27,6 %) et une **meilleure discrimination globale** — ce qui le rend, lui, exploitable en agence.
- **Mais** il ne dispense pas de **regles de validation ciblees** pour les incoherences categorielles, ou il est faible. La conclusion mature est un usage **hybride** : regles simples pour les controles evidents (age, coherence marche/residence), modele statistique pour les anomalies multivariees et le controle du volume d'alertes.

## 8. Limites restantes

- **Donnees d'entrainement simulees** : le modele apprend une distribution plausible, pas le comportement reel de clients BIAT. A rejouer sur historique reel des qu'il sera disponible.
- **Anomalies d'evaluation injectees** : la definition d'« anomalie » est celle de la section 2 ; d'autres definitions donneraient d'autres chiffres.
- **Faiblesse categorielle** documentee (section 6).
- **Rappel modere** au reglage actuel, par choix de sobriete des alertes (section 5).

## 9. Reproductibilite

Tout est deterministe (graines fixees). Pour rejouer :

```bash
python -m evaluation.rapport        # regenere ce rapport
python tests/test_ml_evaluation.py  # verrouille les metriques
```

Les metriques ci-dessus sont verrouillees par la suite `tests/test_ml_evaluation.py` : toute degradation notable du modele ferait echouer les tests.
