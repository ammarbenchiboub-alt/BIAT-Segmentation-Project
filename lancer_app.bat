REM =========================================================================
REM  IMPORTANT : renommez ce fichier en "lancer_app.bat" (enlevez le .txt),
REM  puis double-cliquez dessus pour lancer l'application.
REM =========================================================================
@echo off
chcp 65001 >nul
title BIAT - Segmentation client
cd /d "%~dp0"
echo ============================================================
echo   BIAT - Application de segmentation client (Note 2023-06)
echo ============================================================
echo.
echo [1/2] Installation des dependances (1-2 min la premiere fois)...
python -m pip install -r requirements.txt
echo.
echo [2/2] Lancement de l'application dans le navigateur...
python -m streamlit run app.py
pause
