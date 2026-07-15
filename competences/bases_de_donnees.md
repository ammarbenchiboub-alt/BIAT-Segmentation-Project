# Bases de donnees

## Description

Conception de schemas SQLite pour un stockage persistant, transactionnel et append-only (aucune modification ni suppression possible cote application).

## Technologies

- SQLite
- sqlite3 (Python stdlib)
- SQL (CREATE TABLE, transactions, requetes parametrees)

## Fichiers

- `audit/journal.py`
- `gouvernance/workflow_seuils.py`

## Exemples concrets

- Table journal en ajout seul, avec chainage de hash entre lignes.
- Table propositions avec cycle de vie (EN_ATTENTE / VALIDEE / REJETEE).
- Requetes parametrees (protection contre l'injection SQL).

## Niveau

Schemas concus et testes (insertion, lecture, verification d'integrite).
