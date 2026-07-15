# BIAT - Segmentation client : installation (pour un nouveau poste)

Application Python + Streamlit. Aucune connaissance technique requise.

## Etape 1 - Installer Python (une seule fois)
- Telecharger Python : https://www.python.org/downloads/
- Pendant l'installation, COCHER "Add Python to PATH", puis Installer.

## Etape 2 - Preparer le lanceur
- Dans le dossier, il y a un fichier "lancer_app_RENOMMER_en_.bat.txt".
- Renommez-le en "lancer_app.bat" (supprimez le ".txt" a la fin).
  (Le .bat a ete livre en .txt car les messageries bloquent les .bat.)

## Etape 3 - Lancer
- Double-cliquer sur "lancer_app.bat".
- La premiere fois, il installe les dependances (1 a 2 min).
- L'application s'ouvre dans le navigateur (http://localhost:8501).
- Pour arreter : fermer la fenetre noire ou Ctrl + C.

## Lancement manuel (sans le .bat)
Ouvrir un terminal dans le dossier, puis :
```
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Remarque
La seule source de regles est config/regles_segmentation.json (Note BIAT
2023-06). La page Parametrage permet de modifier seuils et professions sans
toucher au code.
