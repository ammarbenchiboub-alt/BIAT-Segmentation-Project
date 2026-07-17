"""Tests de concurrence et de performance.

Streamlit sert CHAQUE SESSION DANS UN THREAD du meme processus : deux
conseillers qui utilisent l'application au meme instant executent reellement le
meme code en parallele. Ce n'est pas un cas theorique, et c'est precisement ce
que cette suite verifie.

Ces tests sont des NON-REGRESSIONS de defauts reellement constates lors de la
revue d'architecture :

  1. Ecritures concurrentes du journal : 19 sur 20 echouaient
     (PermissionError). Cause : toutes les ecritures de l'ancre passaient par
     le meme fichier temporaire "ancre.json.tmp", et aucun verrou ne serialisait
     les threads.
  2. Fourche de la chaine de hash : deux ecrivains simultanes lisaient le meme
     hash precedent et produisaient deux entrees referencant le meme parent --
     alteration irreversible, signalee ensuite a tort par verifier_integrite.
  3. Compteur d'echecs non deterministe : 20 tentatives paralleles n'en
     comptabilisaient que 10 (mises a jour perdues).
  4. Double validation appliquee deux fois : deux administrateurs confirmant au
     meme instant validaient tous deux la meme proposition.
  5. Import en masse : 27,7 ms par ligne (un fsync et une relecture du fichier
     de regles PAR LIGNE), soit ~138 s pour 5 000 lignes.
"""
from __future__ import annotations

import os
import sys
import threading
import time

from _outils import ModulesRediriges, Resultats, dossier_temporaire

import core.rules_loader as rules_loader
from audit import journal
from auth import tentatives, utilisateurs
from gouvernance import workflow_seuils

UTILISATEUR = {"identifiant": "u1", "nom": "U", "role": "conseiller"}
ADMIN1 = {"identifiant": "admin1", "nom": "Admin 1", "role": "admin"}
ADMIN2 = {"identifiant": "admin2", "nom": "Admin 2", "role": "admin"}
ADMIN3 = {"identifiant": "admin3", "nom": "Admin 3", "role": "admin"}


def _en_parallele(cible, arguments: list) -> list:
    """Lance `cible` en parallele sur chaque jeu d'arguments et renvoie les
    exceptions levees. Les threads demarrent quasi simultanement pour
    maximiser les chances de collision."""
    erreurs = []
    depart = threading.Barrier(len(arguments))

    def _executer(args):
        try:
            depart.wait(timeout=10)
            cible(*args)
        except Exception as exc:  # noqa: BLE001
            erreurs.append(repr(exc))

    threads = [threading.Thread(target=_executer, args=(a,)) for a in arguments]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return erreurs


def run() -> bool:
    r = Resultats("concurrence & performance")
    tmp = dossier_temporaire()

    # ================================================================== #
    # 1. Ecritures concurrentes du journal d'audit
    # ================================================================== #
    with ModulesRediriges(
        (journal, "CHEMIN_JOURNAL", os.path.join(tmp, "j1.sqlite3")),
        (journal, "CHEMIN_ANCRE", os.path.join(tmp, "a1.json")),
    ):
        def ecrire(i):
            journal.enregistrer("SIM", UTILISATEUR, {"Marche": "PART", "Age": i},
                                "Classe Moyenne", "Les salaries", "R1")

        erreurs = _en_parallele(ecrire, [(i,) for i in range(20)])
        r.egal("20 ecritures concurrentes : aucune exception", erreurs[:1], [])
        r.egal("  les 20 entrees sont bien presentes", journal.compter(), 20)
        ok, msg = journal.verifier_integrite()
        r.verifier("  la chaine de hash n'a pas fourche", ok, msg)

        # Aucun fichier temporaire d'ancre laisse derriere.
        residus = [f for f in os.listdir(tmp) if f.endswith(".tmp")]
        r.egal("  aucun fichier temporaire orphelin", residus, [])

    # ================================================================== #
    # 2. Melange d'ecritures individuelles et de lots
    # ================================================================== #
    with ModulesRediriges(
        (journal, "CHEMIN_JOURNAL", os.path.join(tmp, "j2.sqlite3")),
        (journal, "CHEMIN_ANCRE", os.path.join(tmp, "a2.json")),
    ):
        def individuelle(i):
            journal.enregistrer("SIM", UTILISATEUR, {"Marche": "PART", "Age": i},
                                "Grand Public", "Particuliers", "R2")

        def lot(i):
            lignes = [{"Marche": "PRO", "Age": 40, "Segment": "Premium",
                       "Sous_segment": "Premium", "Regle": "R3"} for _ in range(5)]
            journal.enregistrer_lot("IMPORT_MASSE", UTILISATEUR, lignes)

        travaux = [(individuelle, (i,)) for i in range(5)] + [(lot, (i,)) for i in range(3)]

        def executer(fn, args):
            fn(*args)

        erreurs = _en_parallele(executer, travaux)
        r.egal("individuelles + lots en parallele : aucune exception", erreurs[:1], [])
        r.egal("  total attendu (5 + 3x5)", journal.compter(), 20)
        ok, msg = journal.verifier_integrite()
        r.verifier("  chaine et ancre coherentes", ok, msg)

    # ================================================================== #
    # 3. Performance de l'import en masse
    # ================================================================== #
    with ModulesRediriges(
        (journal, "CHEMIN_JOURNAL", os.path.join(tmp, "j3.sqlite3")),
        (journal, "CHEMIN_ANCRE", os.path.join(tmp, "a3.json")),
    ):
        lignes = [{"Marche": "PART", "Age": 30, "MMM": 1000, "VRD": 0,
                   "Segment": "Classe Moyenne", "Sous_segment": "Les salaries",
                   "Regle": "R"} for _ in range(300)]

        # Le fichier de regles ne doit etre lu qu'UNE fois par lot, pas une
        # fois par ligne : toutes les decisions d'un lot partagent, par
        # construction, la meme version des regles.
        compteur = {"n": 0}
        original = rules_loader.empreinte_regles

        def compter_lectures(*a, **k):
            compteur["n"] += 1
            return original(*a, **k)

        with ModulesRediriges((rules_loader, "empreinte_regles", compter_lectures)):
            debut = time.time()
            journal.enregistrer_lot("IMPORT_MASSE", UTILISATEUR, lignes)
            duree = time.time() - debut

        r.egal("import de 300 lignes : le fichier de regles est lu 1 seule fois",
               compteur["n"], 1)
        r.egal("  les 300 entrees sont ecrites", journal.compter(), 300)
        # Seuil large : on garde une marge confortable par rapport aux machines
        # lentes, tout en detectant un retour au regime "un fsync par ligne"
        # (qui mesurait 8,3 s pour ce meme lot).
        r.verifier(f"  duree raisonnable ({duree:.2f}s, seuil 3s, avant correction : 8,3s)",
                   duree < 3.0)
        ok, msg = journal.verifier_integrite()
        r.verifier("  chaine intacte apres un gros lot", ok, msg)

    # ================================================================== #
    # 4. Attaque par force brute parallelisee
    # ================================================================== #
    with ModulesRediriges(
        (utilisateurs, "CHEMIN_UTILISATEURS", os.path.join(tmp, "u.json")),
        (tentatives, "CHEMIN_TENTATIVES", os.path.join(tmp, "t.sqlite3")),
        (tentatives, "MAX_TENTATIVES", 5),
    ):
        resultats = []

        def attaquer(i):
            resultats.append(utilisateurs.authentifier("admin1", f"essai{i}"))

        erreurs = _en_parallele(attaquer, [(i,) for i in range(20)])
        r.egal("20 tentatives paralleles : aucune exception", erreurs[:1], [])
        testes = [x for x in resultats if not x["verrouille"]]
        r.verifier(f"  au plus 5 mots de passe reellement testes ({len(testes)})",
                   len(testes) <= 5)
        r.egal("  compteur d'echecs exact (etait non deterministe : 10/20)",
               tentatives.echecs_consecutifs("admin1"), 20)
        r.verifier("  le compte est verrouille", tentatives.etat_verrouillage("admin1")[0])
        r.egal("  les 20 tentatives sont toutes journalisees",
               len(tentatives.lister_echecs()), 20)

    # ================================================================== #
    # 5. Double validation concurrente (Maker-Checker)
    # ================================================================== #
    with ModulesRediriges(
        (workflow_seuils, "CHEMIN_WORKFLOW", os.path.join(tmp, "p.sqlite3")),
    ):
        regles = {"marches": {}, "listes_professions": {}, "meta": {"version": "9.9"}}
        id_prop = workflow_seuils.proposer(ADMIN1, regles, "Proposition disputee")

        succes = []

        def confirmer(admin):
            ok, _msg, _r = workflow_seuils.confirmer(id_prop, admin)
            if ok:
                succes.append(admin["identifiant"])

        erreurs = _en_parallele(confirmer, [(ADMIN2,), (ADMIN3,), (ADMIN2,), (ADMIN3,)])
        r.egal("4 confirmations concurrentes : aucune exception", erreurs[:1], [])
        r.egal("  UNE SEULE confirmation aboutit (pas de double application)",
               len(succes), 1)
        r.egal("  statut final VALIDEE",
               workflow_seuils.obtenir(id_prop)["statut"], "VALIDEE")

        # Le proposant ne peut jamais confirmer, meme en concurrence.
        id_prop2 = workflow_seuils.proposer(ADMIN1, regles, "Auto-confirmation concurrente")
        succes2 = []

        def confirmer2(admin):
            ok, _m, _r = workflow_seuils.confirmer(id_prop2, admin)
            if ok:
                succes2.append(admin["identifiant"])

        _en_parallele(confirmer2, [(ADMIN1,), (ADMIN1,), (ADMIN1,)])
        r.egal("  la separation des taches tient sous concurrence", succes2, [])
        r.egal("  la proposition reste EN_ATTENTE",
               workflow_seuils.obtenir(id_prop2)["statut"], "EN_ATTENTE")

        # Confirmation et rejet simultanes : un seul des deux l'emporte.
        id_prop3 = workflow_seuils.proposer(ADMIN1, regles, "Confirmation vs rejet")
        issues = []

        def confirmer3(_):
            ok, _m, _r = workflow_seuils.confirmer(id_prop3, ADMIN2)
            if ok:
                issues.append("VALIDEE")

        def rejeter3(_):
            ok, _m = workflow_seuils.rejeter(id_prop3, ADMIN3)
            if ok:
                issues.append("REJETEE")

        _en_parallele(lambda fn: fn(None), [(confirmer3,), (rejeter3,)])
        r.egal("  confirmation et rejet simultanes : une seule issue", len(issues), 1)
        r.egal("  le statut final correspond a l'issue retenue",
               workflow_seuils.obtenir(id_prop3)["statut"], issues[0] if issues else "?")

    return r.bilan()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
