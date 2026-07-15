# Architecture logicielle

## Description

Conception d'un moteur de regles metier decouple, pilote par une configuration declarative, avec versionnement et rollback controle.

## Technologies

- regles declaratives (JSON, priorites, first-match-wins)
- separation des responsabilites (dependances a sens unique)
- versionnement de configuration

## Fichiers

- `config/regles_segmentation.json`
- `core/engine.py`
- `gouvernance/versions.py`

## Exemples concrets

- Moteur unique (core.engine) sans dependance vers l'IA, l'audit ou l'UI.
- config/regles_segmentation.json comme source unique de verite (aucune regle en dur).
- Historique horodate des versions de regles avec restauration via double validation.

## Niveau

Architecture appliquee et respectee sur l'ensemble du projet (contrainte non negociable).
