"""Lanceur de la totalite des tests.

    python tests/run_all.py

Volontairement sans dependance externe (pas de pytest) : la seule facon de
lancer les tests reste "python", exactement comme avant. Ajouter une
dependance de test aurait contredit l'objectif de reproductibilite des
dependances (requirements.txt fige).

Chaque module de test est isole : il ecrit dans un dossier temporaire et ne
touche jamais au journal d'audit, aux comptes ni aux regles reelles.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import test_analyse_portefeuille
import test_audit
import test_auth
import test_cache
import test_chatbot
import test_concurrence
import test_conformite
import test_gouvernance
import test_explicabilite
import test_import
import test_ml
import test_ml_evaluation
import test_moteur
import test_presentation
import test_referentiel

SUITES = [
    ("Moteur de segmentation (non-regression metier)", test_moteur.run),
    ("Conformite metier a la Note BIAT 2023-06", test_conformite.run),
    ("Authentification & protection force brute", test_auth.run),
    ("Integrite du journal d'audit", test_audit.run),
    ("Gouvernance : Maker-Checker & transactionnel", test_gouvernance.run),
    ("Cache du moteur & invalidation", test_cache.run),
    ("Concurrence & performance", test_concurrence.run),
    ("Module Machine Learning", test_ml.run),
    ("Evaluation du modele ML (Isolation Forest)", test_ml_evaluation.run),
    ("Chatbot expert metier", test_chatbot.run),
    ("Import de fichiers (CSV / Excel multi-feuilles)", test_import.run),
    ("Smart Response Renderer (presentation)", test_presentation.run),
    ("Explicabilite & fiche de decision", test_explicabilite.run),
    ("Referentiel BIAT (source unique)", test_referentiel.run),
    ("Analyse de portefeuille (structure & recommandations)", test_analyse_portefeuille.run),
]


def main() -> int:
    debut = time.time()
    resultats = []
    for titre, executer in SUITES:
        print("\n" + "=" * 72)
        print(f"  {titre}")
        print("=" * 72)
        try:
            resultats.append((titre, bool(executer())))
        except Exception as exc:  # noqa: BLE001
            print(f"[ERREUR] la suite a leve une exception : {exc}")
            import traceback
            traceback.print_exc()
            resultats.append((titre, False))

    print("\n" + "=" * 72)
    print("  BILAN GLOBAL")
    print("=" * 72)
    for titre, ok in resultats:
        print(f"  [{'OK ' if ok else 'ECHEC'}] {titre}")
    reussies = sum(1 for _, ok in resultats if ok)
    print(f"\n  {reussies}/{len(resultats)} suites reussies en {time.time() - debut:.1f} s")
    return 0 if reussies == len(resultats) else 1


if __name__ == "__main__":
    sys.exit(main())
