# Genie logiciel / qualite

## Description

Discipline de tests et de verification systematique avant chaque livraison, pour garantir la non-regression du moteur metier.

## Technologies

- tests unitaires (Python, assertions)
- tests de non-regression
- verification fonctionnelle (smoke tests)

## Fichiers

- `tests/test_moteur.py`

## Exemples concrets

- 31 cas de test couvrant l'ensemble des regles de segmentation (PART/PRO/TRE/ENR).
- Execution systematique des 31 tests apres chaque modification du moteur ou des modules annexes.
- Verification de demarrage de l'application (boot test) avant chaque livraison.

## Niveau

Applique en continu tout au long du projet, avant chaque changement livre.
