# Machine Learning

## Description

Module de detection d'anomalies non supervise, complementaire au moteur de regles metier, pour signaler les profils clients statistiquement atypiques sans jamais influencer la decision officielle.

## Technologies

- scikit-learn
- Isolation Forest
- StandardScaler / OneHotEncoder / ColumnTransformer (Pipeline)
- joblib (persistance de modele)
- numpy / pandas

## Fichiers

- `core/ml_anomaly.py`

## Exemples concrets

- Pipeline de preprocessing + Isolation Forest (contamination=0.06).
- Calibration d'un score de confiance (0-100%) via transformation logistique.
- Generation de donnees d'entrainement synthetiques realistes (faute d'historique reel).
- Chargement/sauvegarde automatique du modele pour eviter un reentrainement a chaque lancement.

## Niveau

Modele entraine, calibre et valide iterativement sur des cas metier reels.
