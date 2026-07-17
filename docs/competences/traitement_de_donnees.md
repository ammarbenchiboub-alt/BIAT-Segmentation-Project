# Traitement de donnees

## Description

Generation, validation et nettoyage de donnees tabulaires (Excel/CSV) pour fiabiliser l'import en masse de profils clients.

## Technologies

- openpyxl (generation Excel avec listes deroulantes)
- pandas (lecture/ecriture CSV et Excel)
- validation de schema (types, valeurs autorisees, champs obligatoires)

## Fichiers

- `templates/excel_template.py`
- `validation/csv_validator.py`
- `segmentation/batch.py`

## Exemples concrets

- Modele Excel genere avec listes deroulantes et validations de saisie.
- Detection explicite des champs manquants, invalides ou hors-liste avant segmentation.
- Traitement en masse avec rapport detaille des lignes valides/invalides.

## Niveau

Pipeline complet import -> validation -> segmentation, teste sur un jeu de 33 cas.
