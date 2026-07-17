# Securite applicative

## Description

Authentification, controle d'acces par role, et tracabilite infalsifiable des decisions -- exigences de base d'un controle interne bancaire.

## Technologies

- hachage PBKDF2-HMAC-SHA256 avec sel
- RBAC (role-based access control)
- chainage de hash (registre append-only)
- pattern Maker-Checker (double validation)

## Fichiers

- `auth/utilisateurs.py`
- `auth/__init__.py`
- `audit/journal.py`
- `audit/__init__.py`
- `gouvernance/workflow_seuils.py`

## Exemples concrets

- Comptes avec mots de passe jamais stockes en clair (hash + sel par utilisateur).
- 3 roles (Conseiller / Admin / Auditeur) filtrant l'acces aux pages sensibles.
- Journal d'audit chaine par hash : toute alteration d'une entree est detectable.
- Workflow de double validation : un admin propose, un second confirme obligatoirement.

## Niveau

Implementation fonctionnelle testee (detection de falsification verifiee).
