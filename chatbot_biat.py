"""
╔══════════════════════════════════════════════════════════════════════╗
║   CHATBOT INTELLIGENT DE SEGMENTATION BANCAIRE — BIAT              ║
║   PFE Master 2 Business Analytics                                   ║
║                                                                      ║
║   Fonctionnalités :                                                  ║
║   ✅ Logique segmentation corrigée (OR entre MMM et VRD)           ║
║   ✅ Chatbot expert métier bancaire                                 ║
║   ✅ 3 types de questions : Définitions / Règles / Décision         ║
║   ✅ Validation des données                                         ║
║   ✅ Support français + dialecte tunisien simple                    ║
║   ✅ Règles en JSON exportable                                      ║
║   ✅ Tests automatiques avec cas réels                              ║
╚══════════════════════════════════════════════════════════════════════╝

Installation :
    pip install streamlit pandas

Lancement :
    streamlit run chatbot_biat.py
"""

import streamlit as st
import pandas as pd
import json
import re
import base64
from datetime import datetime

# ══════════════════════════════════════════════════════════════════════
# SECTION 1 — RÈGLES DE SEGMENTATION EN JSON
# Structure exportable et facilement modifiable
# ══════════════════════════════════════════════════════════════════════

REGLES_SEGMENTATION_JSON = {
    "version": "2023-06",
    "source":  "Note PBD N°2023-06 — BIAT",
    "marches": {

        # ── PARTICULIERS ────────────────────────────────────────────
        "PART": {
            "description": "Personnes physiques résidentes tunisiennes non professionnelles",
            "segments": [
                {
                    "segment": "Haut de Gamme",
                    "sous_segments": [
                        {
                            "nom": "Fortunés",
                            "priorite": 1,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "VRD",  "operateur": ">=", "valeur": 500}
                                ]
                            }
                        },
                        {
                            "nom": "Patrimoniaux",
                            "priorite": 2,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "VRD", "operateur": ">=", "valeur": 300},
                                    {"champ": "VRD", "operateur": "<",  "valeur": 500}
                                ]
                            }
                        },
                        {
                            "nom": "Affluent",
                            "priorite": 3,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "age",  "operateur": ">=", "valeur": 30},
                                    {
                                        "logique": "OR",
                                        "regles": [
                                            {"champ": "MMM", "operateur": ">=", "valeur": 4},
                                            {
                                                "logique": "AND",
                                                "regles": [
                                                    {"champ": "VRD", "operateur": ">=", "valeur": 100},
                                                    {"champ": "VRD", "operateur": "<",  "valeur": 300}
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        },
                        {
                            "nom": "Professions Libérales HG",
                            "priorite": 4,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "profession_type", "operateur": "==", "valeur": "liberale"},
                                    {"champ": "VRD", "operateur": ">=", "valeur": 100},
                                    {"champ": "VRD", "operateur": "<",  "valeur": 300}
                                ]
                            }
                        },
                        {
                            "nom": "Épargnants HG",
                            "priorite": 5,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "MMM", "operateur": "==", "valeur": 0},
                                    {"champ": "VRD", "operateur": ">=", "valeur": 100},
                                    {"champ": "VRD", "operateur": "<",  "valeur": 300}
                                ]
                            }
                        }
                    ]
                },
                {
                    "segment": "Classe Moyenne",
                    "sous_segments": [
                        {
                            "nom": "Salariés CM",
                            "priorite": 10,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "age", "operateur": ">=", "valeur": 30},
                                    {
                                        "logique": "OR",   # ← CORRECTION CLEF : OR pas AND
                                        "regles": [
                                            {
                                                "logique": "AND",
                                                "regles": [
                                                    {"champ": "MMM", "operateur": ">=", "valeur": 1},
                                                    {"champ": "MMM", "operateur": "<",  "valeur": 4}
                                                ]
                                            },
                                            {
                                                "logique": "AND",
                                                "regles": [
                                                    {"champ": "VRD", "operateur": ">=", "valeur": 5},
                                                    {"champ": "VRD", "operateur": "<",  "valeur": 100}
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        },
                        {
                            "nom": "Épargnants CM",
                            "priorite": 11,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "MMM", "operateur": "==", "valeur": 0},
                                    {"champ": "VRD", "operateur": ">=", "valeur": 15},
                                    {"champ": "VRD", "operateur": "<",  "valeur": 100}
                                ]
                            }
                        }
                    ]
                },
                {
                    "segment": "Les Jeunes",
                    "sous_segments": [
                        {
                            "nom": "Enfants et Élèves",
                            "priorite": 20,
                            "conditions": {
                                "logique": "AND",
                                "regles": [{"champ": "age", "operateur": "<=", "valeur": 18}]
                            }
                        },
                        {
                            "nom": "Étudiants",
                            "priorite": 21,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "age",       "operateur": "<=",  "valeur": 30},
                                    {"champ": "profession","operateur": "==",  "valeur": "Étudiant"}
                                ]
                            }
                        },
                        {
                            "nom": "JDA Potentiel",
                            "priorite": 22,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "age",             "operateur": "<=", "valeur": 30},
                                    {"champ": "profession_type", "operateur": "==", "valeur": "potentiel"}
                                ]
                            }
                        },
                        {
                            "nom": "Autres JDA",
                            "priorite": 23,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "age", "operateur": "<=", "valeur": 30},
                                    {"champ": "MMM", "operateur": "<",  "valeur": 10}
                                ]
                            }
                        }
                    ]
                },
                {
                    "segment": "Grand Public",
                    "sous_segments": [
                        {
                            "nom": "Particuliers GP",
                            "priorite": 30,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "MMM", "operateur": "<", "valeur": 1},
                                    {"champ": "VRD", "operateur": "<", "valeur": 5}
                                ]
                            }
                        },
                        {
                            "nom": "Clients dormants",
                            "priorite": 31,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "nb_operations_12m", "operateur": "==", "valeur": 0}
                                ]
                            }
                        }
                    ]
                }
            ]
        },

        # ── PROFESSIONNELS ──────────────────────────────────────────
        "PRO": {
            "description": "Personnes physiques résidentes exerçant une activité professionnelle",
            "segments": [
                {
                    "segment": "Haut de Gamme",
                    "sous_segments": [
                        {
                            "nom": "Professionnels HG",
                            "priorite": 1,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "profession_type", "operateur": "==", "valeur": "potentiel"},
                                    {"champ": "VRD",             "operateur": ">=", "valeur": 200}
                                ]
                            }
                        },
                        {
                            "nom": "Patrimoniaux PRO",
                            "priorite": 2,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "VRD", "operateur": ">=", "valeur": 300}
                                ]
                            }
                        },
                        {
                            "nom": "Professions Libérales HG",
                            "priorite": 3,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "profession_type", "operateur": "==", "valeur": "liberale"},
                                    {"champ": "VRD",             "operateur": ">=", "valeur": 100},
                                    {"champ": "VRD",             "operateur": "<",  "valeur": 300}
                                ]
                            }
                        }
                    ]
                },
                {
                    "segment": "Classe Moyenne",
                    "sous_segments": [
                        {
                            "nom": "Commerçants & Artisans CM",
                            "priorite": 10,
                            "conditions": {
                                # ══════════════════════════════════════
                                # CORRECTION CRITIQUE : OR entre MMM et VRD
                                # Un professionnel avec MMM=90 et VRD=3
                                # → MMM ∈ [5,100[ → VRAI → Classe Moyenne ✅
                                # ══════════════════════════════════════
                                "logique": "OR",
                                "regles": [
                                    {
                                        "logique": "AND",
                                        "regles": [
                                            {"champ": "MMM", "operateur": ">=", "valeur": 5},
                                            {"champ": "MMM", "operateur": "<",  "valeur": 100}
                                        ]
                                    },
                                    {
                                        "logique": "AND",
                                        "regles": [
                                            {"champ": "VRD", "operateur": ">=", "valeur": 5},
                                            {"champ": "VRD", "operateur": "<",  "valeur": 200}
                                        ]
                                    }
                                ]
                            }
                        }
                    ]
                },
                {
                    "segment": "Grand Public",
                    "sous_segments": [
                        {
                            "nom": "Commerçants GP",
                            "priorite": 20,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "MMM", "operateur": "<", "valeur": 5},
                                    {"champ": "VRD", "operateur": "<", "valeur": 5}
                                ]
                            }
                        },
                        {
                            "nom": "Clients dormants PRO",
                            "priorite": 21,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "nb_operations_12m", "operateur": "==", "valeur": 0}
                                ]
                            }
                        }
                    ]
                }
            ]
        },

        # ── TRE ─────────────────────────────────────────────────────
        "TRE": {
            "description": "Tunisiens Résidents à l'Étranger",
            "segments": [
                {
                    "segment": "TRE",
                    "sous_segments": [
                        {
                            "nom": "TRE Premium",
                            "priorite": 1,
                            "conditions": {
                                "logique": "OR",
                                "regles": [
                                    {"champ": "profession_type", "operateur": "==", "valeur": "potentiel"},
                                    {"champ": "MMM",             "operateur": ">=", "valeur": 25},
                                    {"champ": "VRD",             "operateur": ">=", "valeur": 50}
                                ]
                            }
                        },
                        {
                            "nom": "TRE Potentiel moyen",
                            "priorite": 2,
                            "conditions": {
                                "logique": "OR",
                                "regles": [
                                    {
                                        "logique": "AND",
                                        "regles": [
                                            {"champ": "MMM", "operateur": ">=", "valeur": 1},
                                            {"champ": "MMM", "operateur": "<",  "valeur": 25}
                                        ]
                                    },
                                    {
                                        "logique": "AND",
                                        "regles": [
                                            {"champ": "VRD", "operateur": ">=", "valeur": 25},
                                            {"champ": "VRD", "operateur": "<",  "valeur": 50}
                                        ]
                                    }
                                ]
                            }
                        },
                        {
                            "nom": "TRE Faible potentiel",
                            "priorite": 3,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "MMM", "operateur": "<", "valeur": 1},
                                    {"champ": "VRD", "operateur": "<", "valeur": 25}
                                ]
                            }
                        },
                        {
                            "nom": "TRE Inactif",
                            "priorite": 4,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "nb_operations_12m", "operateur": "==", "valeur": 0}
                                ]
                            }
                        }
                    ]
                }
            ]
        },

        # ── ENR ─────────────────────────────────────────────────────
        "ENR": {
            "description": "Étrangers Non Résidents",
            "segments": [
                {
                    "segment": "ENR",
                    "sous_segments": [
                        {
                            "nom": "ENR Premium",
                            "priorite": 1,
                            "conditions": {
                                "logique": "OR",
                                "regles": [
                                    {"champ": "MMM", "operateur": ">=", "valeur": 10},
                                    {"champ": "VRD", "operateur": ">=", "valeur": 60}
                                ]
                            }
                        },
                        {
                            "nom": "ENR Potentiel moyen",
                            "priorite": 2,
                            "conditions": {
                                "logique": "OR",
                                "regles": [
                                    {
                                        "logique": "AND",
                                        "regles": [
                                            {"champ": "MMM", "operateur": ">=", "valeur": 5},
                                            {"champ": "MMM", "operateur": "<",  "valeur": 10}
                                        ]
                                    },
                                    {
                                        "logique": "AND",
                                        "regles": [
                                            {"champ": "VRD", "operateur": ">=", "valeur": 30},
                                            {"champ": "VRD", "operateur": "<",  "valeur": 60}
                                        ]
                                    }
                                ]
                            }
                        },
                        {
                            "nom": "ENR Faible potentiel",
                            "priorite": 3,
                            "conditions": {
                                "logique": "AND",
                                "regles": [
                                    {"champ": "MMM", "operateur": "<", "valeur": 5},
                                    {"champ": "VRD", "operateur": "<", "valeur": 30}
                                ]
                            }
                        }
                    ]
                }
            ]
        }
    }
}

# ══════════════════════════════════════════════════════════════════════
# SECTION 2 — MOTEUR DE SEGMENTATION CORRIGÉ
# Implémentation de la logique OR entre MMM et VRD
# ══════════════════════════════════════════════════════════════════════

# Professions à potentiel (Annexe 4)
PROFESSIONS_POTENTIEL = [
    "médecin généraliste", "médecin spécialiste", "médecin dentiste",
    "médecin vétérinaire", "pharmacien", "biologiste", "opticien",
    "avocat", "expert-comptable", "ingénieur", "architecte",
    "notaire", "commissaire aux comptes"
]

# Professions libérales (Annexe 5)
PROFESSIONS_LIBERALES = [
    "médecin généraliste", "médecin spécialiste", "médecin dentiste",
    "médecin vétérinaire", "pharmacien", "biologiste", "expert-comptable"
]


def classifier_profession(profession: str) -> str:
    """
    Classifie une profession en catégorie :
    - 'potentiel'  : Annexe 4 (HG potentiel)
    - 'liberale'   : Annexe 5 (profession libérale)
    - 'etudiant'   : Étudiant
    - 'autre'      : Autres professions
    """
    if not profession:
        return "autre"
    p = profession.lower().strip()
    if p == "étudiant" or p == "etudiant":
        return "etudiant"
    if any(pro in p for pro in PROFESSIONS_POTENTIEL):
        return "potentiel"
    if any(lib in p for lib in PROFESSIONS_LIBERALES):
        return "liberale"
    return "autre"


def valider_client(client: dict) -> tuple[bool, list]:
    """
    Valide les données du client avant segmentation.

    Returns:
        (valide: bool, erreurs: list[str])
    """
    erreurs = []

    # Marché
    marches_valides = ["PART", "PRO", "TRE", "ENR",
                       "Particulier", "Professionnel"]
    marche = str(client.get("marche", "")).strip().upper()
    if not marche or marche not in [m.upper() for m in marches_valides]:
        erreurs.append(f"Marché invalide : '{client.get('marche')}'. Valeurs acceptées : PART, PRO, TRE, ENR")

    # Âge
    age = client.get("age", -1)
    try:
        age = float(age)
        if age < 0 or age > 120:
            erreurs.append(f"Âge invalide : {age}. Doit être entre 0 et 120.")
    except (TypeError, ValueError):
        erreurs.append(f"Âge invalide : '{age}'. Doit être un nombre.")

    # MMM
    mmm = client.get("MMM", -1)
    try:
        mmm = float(mmm)
        if mmm < 0:
            erreurs.append(f"MMM invalide : {mmm}. Doit être >= 0.")
    except (TypeError, ValueError):
        erreurs.append(f"MMM invalide : '{mmm}'. Doit être un nombre positif.")

    # VRD
    vrd = client.get("VRD", -1)
    try:
        vrd = float(vrd)
        if vrd < 0:
            erreurs.append(f"VRD invalide : {vrd}. Doit être >= 0.")
    except (TypeError, ValueError):
        erreurs.append(f"VRD invalide : '{vrd}'. Doit être un nombre positif.")

    return len(erreurs) == 0, erreurs


def _evaluer_condition(condition: dict, client: dict) -> bool:
    """
    Évalue récursivement une condition sur les données client.

    Supporte :
    - Conditions simples  : {champ, operateur, valeur}
    - Conditions composées: {logique: "AND"|"OR", regles: [...]}
    """
    # Condition composée (AND / OR)
    if "logique" in condition:
        logique = condition["logique"].upper()
        regles  = condition.get("regles", [])
        resultats = [_evaluer_condition(r, client) for r in regles]

        if logique == "AND":
            return all(resultats)
        elif logique == "OR":
            return any(resultats)
        return False

    # Condition simple
    champ    = condition.get("champ", "")
    operateur = condition.get("operateur", "==")
    valeur   = condition.get("valeur")

    # Récupérer la valeur du client
    if champ == "profession_type":
        val_client = classifier_profession(client.get("profession", ""))
    elif champ == "nb_operations_12m":
        val_client = int(client.get("nb_operations_12m", 1))
    else:
        try:
            val_client = float(client.get(champ, 0))
        except (TypeError, ValueError):
            return False

    # Appliquer l'opérateur
    ops = {
        ">=": lambda a, b: a >= b,
        "<=": lambda a, b: a <= b,
        ">":  lambda a, b: a > b,
        "<":  lambda a, b: a < b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }
    fn = ops.get(operateur)
    if fn is None:
        return False

    # Comparaison
    if isinstance(valeur, str):
        return fn(str(val_client).lower(), str(valeur).lower())
    return fn(float(val_client), float(valeur))


def get_segment(client: dict) -> dict:
    """
    ╔═══════════════════════════════════════════════════════════╗
    ║  FONCTION PRINCIPALE DE SEGMENTATION                     ║
    ║                                                           ║
    ║  Input  : dictionnaire client                             ║
    ║           {marche, age, MMM, VRD, profession,            ║
    ║            nationalite, residence, nb_operations_12m}    ║
    ║                                                           ║
    ║  Output : {segment, sous_segment, marche,                ║
    ║            justification, est_actif}                     ║
    ║                                                           ║
    ║  CORRECTION CRITIQUE :                                    ║
    ║  Utilise OR entre MMM et VRD comme dans les tableaux     ║
    ║  métier BIAT (pas AND !)                                  ║
    ╚═══════════════════════════════════════════════════════════╝

    Exemple :
        client = {"marche":"PRO","age":40,"MMM":90,"VRD":3,
                  "profession":"Commerçant","nb_operations_12m":24}
        result = get_segment(client)
        # → {"segment":"Classe Moyenne","sous_segment":"Commerçants & Artisans CM"}
    """
    # 1. Validation
    valide, erreurs = valider_client(client)
    if not valide:
        return {
            "segment":      "Erreur de données",
            "sous_segment": "Validation échouée",
            "marche":       client.get("marche", "?"),
            "justification": " | ".join(erreurs),
            "est_actif":    False,
            "erreurs":      erreurs
        }

    # 2. Normaliser le marché
    marche_raw = str(client.get("marche", "PART")).strip().upper()
    marche_map = {
        "PARTICULIER": "PART", "PART": "PART",
        "PROFESSIONNEL": "PRO", "PRO": "PRO",
        "TRE": "TRE", "ENR": "ENR"
    }
    marche = marche_map.get(marche_raw, "PART")

    # 3. Préparer les données normalisées
    client_norm = {
        "marche":           marche,
        "age":              float(client.get("age", 0)),
        "MMM":              float(client.get("MMM", 0)),
        "VRD":              float(client.get("VRD", 0)),
        "profession":       str(client.get("profession", "")),
        "profession_type":  classifier_profession(client.get("profession", "")),
        "nationalite":      str(client.get("nationalite", "Tunisienne")),
        "residence":        str(client.get("residence", "Oui")),
        "nb_operations_12m":int(client.get("nb_operations_12m", 1)),
    }

    # 4. Vérifier dormant en priorité absolue
    if client_norm["nb_operations_12m"] == 0:
        nom_dorm = "Clients dormants PRO" if marche == "PRO" else "Clients dormants"
        if marche == "TRE":
            nom_dorm = "TRE Inactif"
        elif marche == "ENR":
            nom_dorm = "ENR Inactif"
        return {
            "segment":      "Grand Public" if marche in ["PART","PRO"] else marche,
            "sous_segment": nom_dorm,
            "marche":       marche,
            "justification":"nb_operations_12m = 0 → compte dormant détecté automatiquement",
            "est_actif":    False,
            "erreurs":      []
        }

    # 5. Récupérer les règles du marché
    regles_marche = REGLES_SEGMENTATION_JSON["marches"].get(marche, {})
    segments      = regles_marche.get("segments", [])

    # 6. Parcourir les segments par ordre de priorité
    # Les segments sont listés du plus restrictif (HG) au plus général (GP)
    for seg_def in segments:
        segment_nom  = seg_def["segment"]
        sous_segs    = sorted(seg_def["sous_segments"], key=lambda x: x["priorite"])

        for ss in sous_segs:
            condition = ss["conditions"]
            if _evaluer_condition(condition, client_norm):
                # ✅ Segment trouvé
                justif = _construire_justification(ss["nom"], client_norm)
                return {
                    "segment":      segment_nom,
                    "sous_segment": ss["nom"],
                    "marche":       marche,
                    "justification":justif,
                    "est_actif":    True,
                    "erreurs":      []
                }

    # 7. Fallback : Grand Public
    return {
        "segment":      "Grand Public",
        "sous_segment": "Profil non classifié",
        "marche":       marche,
        "justification":"Aucune règle spécifique ne correspond — classé Grand Public par défaut",
        "est_actif":    True,
        "erreurs":      []
    }


def _construire_justification(sous_segment: str, client: dict) -> str:
    """Construit une explication lisible de la segmentation."""
    age = client["age"]; mmm = client["MMM"]; vrd = client["VRD"]
    prof = client["profession"]; marche = client["marche"]

    justifs = {
        "Fortunés":              f"Particulier · VRD {vrd} mD ≥ 500 mD",
        "Patrimoniaux":          f"VRD {vrd} mD ∈ [300, 500[ mD",
        "Affluent":              f"Particulier · âge {age} ans ≥ 30 · MMM {mmm} mD OU VRD {vrd} mD ∈ [100,300[ mD",
        "Professions Libérales HG": f"Profession libérale ({prof}) · VRD {vrd} mD ∈ [100,300[ mD",
        "Épargnants HG":         f"Épargnant exclusif · MMM=0 · VRD {vrd} mD ∈ [100,300[ mD",
        "Professionnels HG":     f"Professionnel à potentiel ({prof}) · VRD {vrd} mD ≥ 200 mD",
        "Patrimoniaux PRO":      f"Professionnel · VRD {vrd} mD ≥ 300 mD",
        "Salariés CM":           f"Particulier · âge {age} ≥ 30 · MMM {mmm} mD ∈ [1,4[ mD OU VRD {vrd} mD ∈ [5,100[ mD",
        "Épargnants CM":         f"MMM=0 · VRD {vrd} mD ∈ [15,100[ mD",
        "Commerçants & Artisans CM": f"PRO · MMM {mmm} mD ∈ [5,100[ mD OU VRD {vrd} mD ∈ [5,200[ mD ← (OR appliqué)",
        "Enfants et Élèves":     f"Âge {age} ans ≤ 18 ans",
        "Étudiants":             f"Étudiant · âge {age} ans ≤ 30 ans",
        "JDA Potentiel":         f"Âge {age} ans ≤ 30 · profession à potentiel ({prof})",
        "Autres JDA":            f"Âge {age} ans ≤ 30 · MMM {mmm} mD < 10 mD",
        "Particuliers GP":       f"MMM {mmm} mD < 1 et VRD {vrd} mD < 5 mD",
        "Commerçants GP":        f"PRO · MMM {mmm} mD < 5 et VRD {vrd} mD < 5 mD",
        "TRE Premium":           f"TRE · MMM {mmm} mD ≥ 25 OU VRD {vrd} mD ≥ 50",
        "TRE Potentiel moyen":   f"TRE · MMM {mmm} mD ∈ [1,25[ OU VRD {vrd} mD ∈ [25,50[",
        "TRE Faible potentiel":  f"TRE · MMM {mmm} mD < 1 et VRD {vrd} mD < 25",
        "ENR Premium":           f"ENR · MMM {mmm} mD ≥ 10 OU VRD {vrd} mD ≥ 60",
        "ENR Potentiel moyen":   f"ENR · MMM {mmm} mD ∈ [5,10[ OU VRD {vrd} mD ∈ [30,60[",
        "ENR Faible potentiel":  f"ENR · MMM {mmm} mD < 5 et VRD {vrd} mD < 30",
    }
    return justifs.get(sous_segment, f"Segment : {sous_segment} — Marché {marche}")


# ══════════════════════════════════════════════════════════════════════
# SECTION 3 — BASE DE CONNAISSANCES DU CHATBOT
# Dictionnaire structuré pour répondre aux 3 types de questions
# ══════════════════════════════════════════════════════════════════════

BASE_CONNAISSANCES = {

    # ── TYPE 1 : DÉFINITIONS ────────────────────────────────────────
    "definitions": {
        "mmm": {
            "mots_cles": ["mmm","mouvement","mensuel","moyen","revenus"],
            "reponse": """📊 **MMM — Mouvements Mensuels Moyens**

Le MMM représente la **moyenne mensuelle des mouvements créditeurs** du compte client, calculée sur la période dans le système T24.

**Unité :** mD (milliers de Dinars Tunisiens)
**Exemple :** MMM = 3 mD signifie 3 000 DT de mouvements par mois en moyenne.

**Rôle dans la segmentation :**
- MMM ≥ 4 mD → critère pour être Affluent (PART, âge ≥ 30)
- MMM ∈ [1,4[ mD → critère Salarié Classe Moyenne
- MMM ∈ [5,100[ mD → critère Commerçant Classe Moyenne (PRO)

⚠️ **Important :** Dans les règles métier, la condition est **MMM OU VRD** (pas AND).
Cela signifie qu'une seule des deux conditions suffit pour valider le segment."""
        },
        "vrd": {
            "mots_cles": ["vrd","avoirs","dépôts","épargne","patrimoine","avoir"],
            "reponse": """💰 **VRD — Valeur des avoirs en Dépôts (Total Avoirs Stables)**

Le VRD représente le **total des avoirs stables** du client :
→ Dépôts à vue + Dépôts épargne + Dépôts à terme

**Unité :** mD (milliers de Dinars Tunisiens)
**Exemple :** VRD = 150 mD signifie 150 000 DT d'avoirs bancaires.

**Rôle dans la segmentation :**
- VRD ≥ 500 mD → Fortunés
- VRD ∈ [300,500[ mD → Patrimoniaux
- VRD ∈ [100,300[ mD → Affluent OU Professions Libérales HG

⚠️ **Important :** La condition est **MMM OU VRD**.
Un client avec VRD très élevé mais MMM faible peut quand même être Haut de Gamme."""
        },
        "segment": {
            "mots_cles": ["segment","segmentation","c'est quoi","qu'est-ce","kesma","chnoua"],
            "reponse": """🏷️ **Segment — Définition**

Un **segment** est une catégorie qui regroupe des clients ayant des caractéristiques financières et socio-démographiques similaires.

**Les 4 segments principaux (PART & PRO) :**
1. 🏆 **Haut de Gamme** — Clients fortunés, avoirs élevés
2. 🟢 **Classe Moyenne** — Revenus intermédiaires
3. 🔵 **Grand Public** — Revenus modestes
4. 🟣 **Les Jeunes** — Moins de 30 ans

**Chaque segment a des sous-segments** selon des seuils précis de MMM et VRD.

**Objectif :** Personnaliser l'offre bancaire et optimiser la relation client."""
        },
        "sous_segment": {
            "mots_cles": ["sous-segment","sous segment","sous_segment"],
            "reponse": """📁 **Sous-segment — Définition**

Un **sous-segment** est une subdivision plus fine d'un segment.

**Exemple pour Haut de Gamme :**
- Fortunés (VRD ≥ 500 mD)
- Patrimoniaux (VRD 300–500 mD)
- Affluent (âge ≥ 30 + MMM ≥ 4 mD)
- Professions Libérales HG
- Épargnants HG

**Exemple pour Classe Moyenne :**
- Salariés CM
- Épargnants CM
- Commerçants & Artisans CM"""
        },
        "md": {
            "mots_cles": ["md","millier","dinar","unité","mille","mdinar"],
            "reponse": """💵 **mD — Milliers de Dinars Tunisiens**

**mD** est l'unité utilisée pour exprimer les montants dans la segmentation BIAT.

| mD | Équivalent en DT |
|----|-----------------|
| 1 mD | 1 000 DT |
| 4 mD | 4 000 DT |
| 100 mD | 100 000 DT |
| 500 mD | 500 000 DT |

**Dans les formulaires**, saisissez toujours en mD.
Exemple : si le client a 50 000 DT d'avoirs, saisissez VRD = 50."""
        },
        "tre": {
            "mots_cles": ["tre","étranger","résidant","expatrié"],
            "reponse": """🌍 **TRE — Tunisiens Résidents à l'Étranger**

Les **TRE** sont des Tunisiens vivant à l'étranger qui maintiennent une relation bancaire avec la BIAT en Tunisie.

**4 sous-segments :**
- **TRE Premium** : Profession à potentiel OU MMM ≥ 25 mD OU VRD ≥ 50 mD
- **TRE Potentiel moyen** : MMM ∈ [1,25[ mD OU VRD ∈ [25,50[ mD
- **TRE Faible potentiel** : MMM < 1 mD ET VRD < 25 mD
- **TRE Inactif** : Aucun mouvement depuis 1 an"""
        },
        "enr": {
            "mots_cles": ["enr","non résident","étranger"],
            "reponse": """🌐 **ENR — Étrangers Non Résidents**

Les **ENR** sont des étrangers dont le séjour en Tunisie ne dépasse pas 3 mois consécutifs.

**3 sous-segments :**
- **ENR Premium** : MMM ≥ 10 mD OU VRD ≥ 60 mD
- **ENR Potentiel moyen** : MMM ∈ [5,10[ mD OU VRD ∈ [30,60[ mD
- **ENR Faible potentiel** : MMM < 5 mD ET VRD < 30 mD"""
        },
        "jda": {
            "mots_cles": ["jda","jeune diplômé","diplômé","jeune"],
            "reponse": """🎓 **JDA — Jeune Diplômé à Potentiel**

Les **JDA (Jeunes Diplômés à Fort Potentiel)** sont des clients de moins de 30 ans exerçant une profession à haut potentiel.

**Professions à potentiel (Annexe 4) :**
Médecin, Pharmacien, Ingénieur, Avocat, Expert-comptable, Architecte...

**Pourquoi c'est important ?**
Les JDA sont les futurs clients Haut de Gamme de la banque.
La BIAT leur propose des offres spéciales pour les fidéliser tôt."""
        }
    },

    # ── TYPE 2 : RÈGLES DE SEGMENTATION ────────────────────────────
    "regles": {
        "affluent": {
            "mots_cles": ["affluent","condition affluent","règle affluent"],
            "reponse": """🏆 **Règles du segment Affluent**

**Marché :** Particuliers (PART)

**Conditions requises :**
```
âge ≥ 30 ans
ET
(MMM ≥ 4 mD  OU  VRD ∈ [100, 300[ mD)
```

**Exemples :**
| Âge | MMM | VRD | Affluent ? |
|-----|-----|-----|------------|
| 35  | 5   | 20  | ✅ Oui (MMM ≥ 4) |
| 35  | 1   | 150 | ✅ Oui (VRD ∈ [100,300[) |
| 25  | 10  | 200 | ❌ Non (âge < 30) |
| 35  | 1   | 50  | ❌ Non (ni MMM ni VRD) |

⚠️ **La condition entre MMM et VRD est un OU.**
Une seule des deux suffit (si l'âge est ≥ 30)."""
        },
        "haut de gamme": {
            "mots_cles": ["haut de gamme","hg","fortuné","patrimoniaux"],
            "reponse": """🏆 **Règles du segment Haut de Gamme**

**Sous-segments par ordre de priorité :**

**1. Fortunés** (PART) : VRD ≥ 500 mD
**2. Patrimoniaux** : VRD ∈ [300, 500[ mD
**3. Affluent** (PART) : âge ≥ 30 ET (MMM ≥ 4 mD OU VRD ∈ [100,300[ mD)
**4. Professions Libérales HG** : Profession libérale ET VRD ∈ [100,300[ mD
**5. Professionnels HG** (PRO) : Profession à potentiel ET VRD ≥ 200 mD
**6. Épargnants HG** : MMM = 0 ET VRD ∈ [100,300[ mD"""
        },
        "classe moyenne": {
            "mots_cles": ["classe moyenne","cm","salarié","commerçant"],
            "reponse": """🟢 **Règles du segment Classe Moyenne**

**Pour Particuliers (PART) :**
- **Salariés CM** : âge ≥ 30 ET (MMM ∈ [1,4[ mD OU VRD ∈ [5,100[ mD)
- **Épargnants CM** : MMM = 0 ET VRD ∈ [15,100[ mD

**Pour Professionnels (PRO) :**
- **Commerçants & Artisans CM** :
  👉 **MMM ∈ [5,100[ mD OU VRD ∈ [5,200[ mD** ← (OR !)

⚠️ **Correction importante :**
L'ancien code utilisait AND pour PRO Classe Moyenne → FAUX.
La règle correcte est **OR** : si MMM est dans la plage OU si VRD est dans la plage.

**Exemple :** MMM=90 mD, VRD=3 mD → MMM ∈ [5,100[ ✅ → **Classe Moyenne** ✅"""
        },
        "grand public": {
            "mots_cles": ["grand public","gp","bas revenus"],
            "reponse": """🔵 **Règles du segment Grand Public**

**Particuliers (PART) :**
- MMM < 1 mD ET VRD < 5 mD → Particuliers GP
- nb_operations_12m = 0 → Clients dormants

**Professionnels (PRO) :**
- MMM < 5 mD ET VRD < 5 mD → Commerçants GP
- nb_operations_12m = 0 → Clients dormants PRO

**Note :** C'est le segment par défaut quand aucune autre règle ne s'applique."""
        },
        "or": {
            "mots_cles": ["ou","or","condition ou","mmm ou vrd","correction"],
            "reponse": """⚠️ **Correction critique : le OU entre MMM et VRD**

**Le problème :**
L'ancienne logique utilisait **AND** entre MMM et VRD.
Cela signifiait que les DEUX conditions devaient être vraies.

**La bonne logique :**
Les tableaux métier BIAT utilisent **OU** (OR).
Une seule condition suffit pour valider le segment.

**Exemple concret :**
```
Client : PRO, MMM=90 mD, VRD=3 mD
Règle : MMM ∈ [5,100[ mD  OU  VRD ∈ [5,200[ mD

Avec AND : (90 ∈ [5,100[ = ✅) AND (3 ∈ [5,200[ = ❌) → ❌ FAUX
Avec OR  : (90 ∈ [5,100[ = ✅) OR  (3 ∈ [5,200[ = ❌) → ✅ CORRECT
```

**Résultat attendu :** Classe Moyenne — Commerçants & Artisans CM ✅"""
        }
    }
}


def rechercher_reponse_kb(question: str) -> str | None:
    """
    Recherche une réponse dans la base de connaissances.
    Retourne None si aucune réponse n'est trouvée.
    """
    q = question.lower().strip()

    # Chercher dans les définitions
    for _, item in BASE_CONNAISSANCES["definitions"].items():
        if any(mot in q for mot in item["mots_cles"]):
            return item["reponse"]

    # Chercher dans les règles
    for _, item in BASE_CONNAISSANCES["regles"].items():
        if any(mot in q for mot in item["mots_cles"]):
            return item["reponse"]

    return None


# ══════════════════════════════════════════════════════════════════════
# SECTION 4 — ANALYSEUR DE PROFIL CLIENT DANS LE CHAT
# Détecte les données client dans le texte et segmente automatiquement
# ══════════════════════════════════════════════════════════════════════

def extraire_profil_du_texte(texte: str) -> dict | None:
    """
    Tente d'extraire un profil client depuis le texte de l'utilisateur.
    Supporte les formats :
    - "MMM=90, VRD=3, PRO, age=40"
    - "client : marché PRO, 40 ans, MMM 90, VRD 3"
    - "j'ai un client professionnel de 40 ans avec MMM 90 et VRD 3"
    """
    profil = {}
    texte_lower = texte.lower()

    # Extraction du marché
    for m in ["pro", "professionnel", "part", "particulier", "tre", "enr"]:
        if m in texte_lower:
            mapping = {
                "pro": "PRO", "professionnel": "PRO",
                "part": "PART", "particulier": "PART",
                "tre": "TRE", "enr": "ENR"
            }
            profil["marche"] = mapping[m]
            break

    # Extraction de l'âge
    age_match = re.search(r'(?:age|âge|ans)[=:\s]+(\d+)', texte_lower)
    if not age_match:
        age_match = re.search(r'(\d+)\s*ans', texte_lower)
    if age_match:
        profil["age"] = int(age_match.group(1))

    # Extraction du MMM
    mmm_match = re.search(r'mmm[=:\s]+(\d+(?:\.\d+)?)', texte_lower)
    if mmm_match:
        profil["MMM"] = float(mmm_match.group(1))

    # Extraction du VRD
    vrd_match = re.search(r'vrd[=:\s]+(\d+(?:\.\d+)?)', texte_lower)
    if vrd_match:
        profil["VRD"] = float(vrd_match.group(1))

    # Extraction profession
    professions_detectees = [
        "médecin", "pharmacien", "ingénieur", "avocat", "architecte",
        "commerçant", "artisan", "étudiant", "fonctionnaire",
        "expert-comptable", "retraité"
    ]
    for prof in professions_detectees:
        if prof in texte_lower:
            profil["profession"] = prof.capitalize()
            break

    # Valider qu'on a au moins marché + MMM ou VRD
    if "marche" in profil and ("MMM" in profil or "VRD" in profil):
        # Valeurs par défaut
        profil.setdefault("age", 35)
        profil.setdefault("MMM", 0)
        profil.setdefault("VRD", 0)
        profil.setdefault("profession", "Autre")
        profil.setdefault("nationalite", "Tunisienne")
        profil.setdefault("residence", "Oui")
        profil.setdefault("nb_operations_12m", 24)
        return profil

    return None


def generer_reponse_chatbot(question: str) -> str:
    """
    Génère une réponse intelligente du chatbot.

    Logique :
    1. Détection d'un profil client → segmentation automatique
    2. Question de définition → réponse de la KB
    3. Question de règle → réponse de la KB
    4. Question générale → réponse générique intelligente
    """
    q = question.lower().strip()

    # ── 0. Salutations ────────────────────────────────────────────
    if any(w in q for w in ["bonjour","salut","hello","bonsoir","marhba","ahla"]):
        return """👋 **Bonjour !**

Je suis **BIATBot**, votre assistant expert en segmentation bancaire.

Je peux vous aider avec :
- 📚 **Définitions** : MMM, VRD, segment, sous-segment...
- 📏 **Règles** : Conditions pour être Affluent, Classe Moyenne, etc.
- 🔍 **Aide à la décision** : Donnez-moi un profil client et je trouve le segment

**Exemple de question :**
> "Client PRO, age=40, MMM=90, VRD=3 → quel segment ?"

Ou simplement : *"C'est quoi le MMM ?"*"""

    # ── 1. Aide générale ──────────────────────────────────────────
    if any(w in q for w in ["aide","help","comment","quoi faire","sesh"]):
        return """ℹ️ **Comment utiliser BIATBot :**

**Type 1 — Définition :**
> "C'est quoi le MMM ?"
> "Explique-moi le VRD"
> "C'est quoi un JDA ?"

**Type 2 — Règles de segmentation :**
> "Quelles sont les conditions pour être Affluent ?"
> "Règles du segment Haut de Gamme"
> "Pourquoi utiliser OR et pas AND ?"

**Type 3 — Aide à la décision :**
> "Client PRO, MMM=90, VRD=3, age=40 → segment ?"
> "Marché PART, âge 35 ans, MMM=2, VRD=80"
> "j'ai un client TRE avec MMM=30 mD" """

    # ── 2. Détection de profil client ─────────────────────────────
    profil = extraire_profil_du_texte(question)
    if profil:
        result = get_segment(profil)
        seg    = result["segment"]
        sous   = result["sous_segment"]
        justif = result["justification"]
        marche = result["marche"]

        icones = {
            "Haut de Gamme": "🏆", "Classe Moyenne": "🟢",
            "Grand Public":  "🔵", "Les Jeunes":    "🟣",
            "TRE": "🌍", "ENR": "🌐"
        }
        icone = icones.get(seg, "📊")

        return f"""🔍 **Analyse du profil client détecté :**

| Champ | Valeur |
|-------|--------|
| Marché | {marche} |
| Âge | {profil.get('age', '?')} ans |
| MMM | {profil.get('MMM', '?')} mD |
| VRD | {profil.get('VRD', '?')} mD |
| Profession | {profil.get('profession', '?')} |

---

{icone} **Segment attribué : {seg}**
📌 **Sous-segment : {sous}**

**Justification :**
> {justif}

---
💡 *Note : La condition entre MMM et VRD est un **OU** (logique correcte).
Une seule condition suffit pour valider le segment.*"""

    # ── 3. Recherche dans la base de connaissances ────────────────
    reponse_kb = rechercher_reponse_kb(question)
    if reponse_kb:
        return reponse_kb

    # ── 4. Tentative de réponse générique intelligente ────────────
    if any(w in q for w in ["segment","segmentation"]):
        return """📊 **Sur la segmentation bancaire BIAT :**

La segmentation divise les clients en groupes selon leurs caractéristiques.

**4 marchés :** PART (Particuliers) · PRO (Professionnels) · TRE · ENR

**Segments PART/PRO :**
- 🏆 Haut de Gamme (Fortunés, Patrimoniaux, Affluent...)
- 🟢 Classe Moyenne (Salariés, Commerçants & Artisans...)
- 🔵 Grand Public
- 🟣 Les Jeunes (< 30 ans)

**Règle clé :** La condition entre MMM et VRD est un **OU**, pas un AND.

Posez-moi une question spécifique sur un segment pour plus de détails !"""

    if any(w in q for w in ["merci","thank","choukran","شكراً"]):
        return "😊 Avec plaisir ! N'hésitez pas pour toute autre question sur la segmentation BIAT."

    # ── 5. Réponse par défaut ──────────────────────────────────────
    return f"""🤔 Je n'ai pas bien compris votre question.

**Essayez de reformuler avec :**
- Un mot-clé : *MMM, VRD, Affluent, Classe Moyenne, Haut de Gamme, TRE...*
- Un profil : *"PRO, MMM=90, VRD=3, age=40"*

Ou tapez **"aide"** pour voir ce que je sais faire."""


# ══════════════════════════════════════════════════════════════════════
# SECTION 5 — TESTS AUTOMATIQUES
# ══════════════════════════════════════════════════════════════════════

def lancer_tests() -> list:
    """
    Cas de test réels pour valider la logique de segmentation.
    Vérifie notamment le cas critique : MMM=90, VRD=3, PRO → Classe Moyenne
    """
    cas_tests = [
        # ── Cas critique corrigé ──────────────────────────────────
        {
            "description": "🔴 CAS CRITIQUE : PRO, MMM=90, VRD=3 → Classe Moyenne (OR)",
            "client": {"marche":"PRO","age":40,"MMM":90,"VRD":3,
                       "profession":"Commerçant","nb_operations_12m":24},
            "attendu_segment":     "Classe Moyenne",
            "attendu_sous_segment":"Commerçants & Artisans CM"
        },
        # ── Haut de Gamme ─────────────────────────────────────────
        {
            "description": "Fortunés : VRD=600 → Fortunés",
            "client": {"marche":"PART","age":55,"MMM":10,"VRD":600,
                       "profession":"Retraité","nb_operations_12m":10},
            "attendu_segment":     "Haut de Gamme",
            "attendu_sous_segment":"Fortunés"
        },
        {
            "description": "Affluent : age=35, MMM=5 (OR valide)",
            "client": {"marche":"PART","age":35,"MMM":5,"VRD":20,
                       "profession":"Fonctionnaire","nb_operations_12m":30},
            "attendu_segment":     "Haut de Gamme",
            "attendu_sous_segment":"Affluent"
        },
        {
            "description": "Affluent par VRD : age=45, VRD=150 (OR valide)",
            "client": {"marche":"PART","age":45,"MMM":1,"VRD":150,
                       "profession":"Salarié","nb_operations_12m":20},
            "attendu_segment":     "Haut de Gamme",
            "attendu_sous_segment":"Affluent"
        },
        # ── Classe Moyenne ────────────────────────────────────────
        {
            "description": "Salariés CM : PART, age=32, MMM=2",
            "client": {"marche":"PART","age":32,"MMM":2,"VRD":10,
                       "profession":"Fonctionnaire","nb_operations_12m":15},
            "attendu_segment":     "Classe Moyenne",
            "attendu_sous_segment":"Salariés CM"
        },
        {
            "description": "PRO CM par VRD : MMM=2, VRD=50 (OR valide)",
            "client": {"marche":"PRO","age":35,"MMM":2,"VRD":50,
                       "profession":"Artisan","nb_operations_12m":12},
            "attendu_segment":     "Classe Moyenne",
            "attendu_sous_segment":"Commerçants & Artisans CM"
        },
        # ── Grand Public ──────────────────────────────────────────
        {
            "description": "Grand Public : PART, MMM=0.5, VRD=3",
            "client": {"marche":"PART","age":40,"MMM":0.5,"VRD":3,
                       "profession":"Salarié","nb_operations_12m":5},
            "attendu_segment":     "Grand Public",
            "attendu_sous_segment":"Particuliers GP"
        },
        # ── Dormant ───────────────────────────────────────────────
        {
            "description": "Dormant : nb_operations_12m=0",
            "client": {"marche":"PART","age":50,"MMM":2,"VRD":30,
                       "profession":"Salarié","nb_operations_12m":0},
            "attendu_segment":     "Grand Public",
            "attendu_sous_segment":"Clients dormants"
        },
        # ── Les Jeunes ────────────────────────────────────────────
        {
            "description": "JDA Potentiel : age=25, médecin",
            "client": {"marche":"PART","age":25,"MMM":3,"VRD":50,
                       "profession":"Médecin généraliste","nb_operations_12m":18},
            "attendu_segment":     "Les Jeunes",
            "attendu_sous_segment":"JDA Potentiel"
        },
        # ── TRE ───────────────────────────────────────────────────
        {
            "description": "TRE Premium : MMM=30",
            "client": {"marche":"TRE","age":45,"MMM":30,"VRD":10,
                       "profession":"Ingénieur","nb_operations_12m":20},
            "attendu_segment":     "TRE",
            "attendu_sous_segment":"TRE Premium"
        },
        # ── ENR ───────────────────────────────────────────────────
        {
            "description": "ENR Potentiel moyen : MMM=7",
            "client": {"marche":"ENR","age":40,"MMM":7,"VRD":15,
                       "profession":"Autre","nb_operations_12m":8},
            "attendu_segment":     "ENR",
            "attendu_sous_segment":"ENR Potentiel moyen"
        },
    ]

    resultats = []
    for cas in cas_tests:
        result    = get_segment(cas["client"])
        ok_seg    = result["segment"]      == cas["attendu_segment"]
        ok_sous   = result["sous_segment"] == cas["attendu_sous_segment"]
        succes    = ok_seg and ok_sous
        resultats.append({
            "description":        cas["description"],
            "attendu_segment":    cas["attendu_segment"],
            "attendu_sous_segment":cas["attendu_sous_segment"],
            "obtenu_segment":     result["segment"],
            "obtenu_sous_segment":result["sous_segment"],
            "justification":      result["justification"],
            "succes":             succes,
            "emoji":              "✅" if succes else "❌"
        })

    return resultats


# ══════════════════════════════════════════════════════════════════════
# SECTION 6 — INTERFACE STREAMLIT
# ══════════════════════════════════════════════════════════════════════

# ── Constantes couleurs ────────────────────────────────────────────
BIAT_BLUE   = "#002B5C"
BIAT_ORANGE = "#F5A623"
BIAT_GRAY   = "#F4F6F9"

# ── Logo SVG BIAT ─────────────────────────────────────────────────
LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 60" width="160" height="48">
  <rect width="200" height="60" rx="5" fill="#002B5C"/>
  <polygon points="16,8 30,8 20,46 6,46" fill="white" opacity="0.95"/>
  <text x="38" y="38" font-family="Arial Black,Arial" font-weight="900"
        font-size="26" fill="white" letter-spacing="2">BIAT</text>
  <rect y="50" width="200" height="10" fill="#F5A623"/>
</svg>"""
LOGO_B64 = base64.b64encode(LOGO_SVG.encode()).decode()

st.set_page_config(
    page_title="BIATBot — Chatbot Segmentation",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(f"""
<style>
    .stApp {{ background-color: {BIAT_GRAY}; }}
    .biat-header {{
        background: {BIAT_BLUE}; padding: 0; margin-bottom: 20px;
        border-radius: 12px; overflow: hidden;
        box-shadow: 0 4px 20px rgba(0,43,92,0.2);
    }}
    .biat-header-inner {{
        display: flex; align-items: center; justify-content: space-between;
        padding: 16px 24px 12px;
    }}
    .biat-header h2 {{ color: white; margin: 0; font-size: 1.4rem; font-weight: 700; }}
    .biat-header p  {{ color: rgba(255,255,255,0.7); margin: 3px 0 0; font-size: .82rem; }}
    .biat-bar {{ background: {BIAT_ORANGE}; height: 5px; }}
    .stTabs [data-baseweb="tab-list"] {{
        background: white; border-radius: 10px 10px 0 0;
        padding: 5px 8px 0; gap: 4px;
        border-bottom: 2px solid {BIAT_ORANGE};
    }}
    .stTabs [data-baseweb="tab"] {{
        background: {BIAT_GRAY}; border-radius: 8px 8px 0 0;
        font-weight: 600; font-size: .84rem; padding: 7px 16px;
        border: 1px solid #e2e8f0; border-bottom: none;
    }}
    .stTabs [aria-selected="true"] {{
        background: {BIAT_BLUE} !important; color: white !important;
    }}
    .stTabs [data-baseweb="tab-panel"] {{
        background: white; border-radius: 0 0 10px 10px;
        padding: 20px; box-shadow: 0 2px 8px rgba(0,43,92,0.07);
    }}
    .chat-box {{
        background: {BIAT_GRAY}; border-radius: 12px;
        padding: 14px; margin-bottom: 12px;
        border: 1px solid #e2e8f0; max-height: 500px; overflow-y: auto;
    }}
    .msg-user {{
        background: {BIAT_BLUE}; color: white;
        border-radius: 14px 14px 2px 14px;
        padding: 10px 14px; margin: 6px 0 6px 60px;
        font-size: .87rem;
    }}
    .msg-bot {{
        background: white; color: #1A2B4A;
        border-radius: 14px 14px 14px 2px;
        padding: 10px 14px; margin: 6px 60px 6px 0;
        font-size: .87rem; border: 1px solid #e2e8f0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }}
    .msg-nom-bot {{ font-size: .72rem; color: {BIAT_ORANGE}; font-weight: 700; margin-bottom: 3px; }}
    .msg-nom-usr {{ font-size: .72rem; color: rgba(255,255,255,.7); margin-bottom: 3px; text-align: right; }}
    .kpi-card {{
        background: white; border-radius: 10px; padding: 14px;
        text-align: center; border: 1px solid #e2e8f0;
        border-top: 3px solid {BIAT_ORANGE};
        box-shadow: 0 2px 8px rgba(0,43,92,0.07);
    }}
    .kpi-val {{ font-size: 1.8rem; font-weight: 700; color: {BIAT_BLUE}; }}
    .kpi-lbl {{ font-size: .78rem; color: #6B7280; margin-top: 3px; }}
    [data-testid="stSidebar"] {{ background: {BIAT_BLUE} !important; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    [data-testid="stSidebar"] .stButton button {{
        background: {BIAT_ORANGE} !important; color: {BIAT_BLUE} !important;
        font-weight: 700 !important; border: none !important;
    }}
    #MainMenu {{visibility:hidden;}} footer {{visibility:hidden;}}
</style>
""", unsafe_allow_html=True)

# Initialisations session
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "bot", "content": "Bonjour ! 👋 Je suis **BIATBot**, votre assistant expert en segmentation bancaire BIAT.\n\nTapez **aide** pour voir ce que je sais faire, ou posez directement votre question !"}
    ]
if "nb_questions" not in st.session_state:
    st.session_state.nb_questions = 0


def main():
    # ── Header ────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="biat-header">
        <div class="biat-header-inner">
            <img src="data:image/svg+xml;base64,{LOGO_B64}" width="150" alt="BIAT">
            <div>
                <h2>🤖 BIATBot — Assistant de Segmentation</h2>
                <p>Expert métier bancaire · PART · PRO · TRE · ENR · Note PBD N°2023-06</p>
            </div>
        </div>
        <div class="biat-bar"></div>
    </div>
    """, unsafe_allow_html=True)

    # ── Sidebar ───────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center;padding:14px 0 8px;">
            <img src="data:image/svg+xml;base64,{LOGO_B64}" width="150" alt="BIAT">
            <div style="color:rgba(255,255,255,.6);font-size:.72rem;margin-top:8px;">
                PÔLE BANQUE DE DÉTAIL
            </div>
        </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(f"""
        <div style="color:white;font-weight:600;font-size:.85rem;margin-bottom:8px;">
            📊 Statistiques session
        </div>""", unsafe_allow_html=True)

        nb_q = st.session_state.nb_questions
        st.markdown(f"""
        <div class="kpi-card" style="margin-bottom:8px;">
            <div class="kpi-val">{nb_q}</div>
            <div class="kpi-lbl">Questions posées</div>
        </div>""", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("""
        <div style="color:rgba(255,255,255,.8);font-size:.8rem;">
            <strong>💡 Questions exemple :</strong><br><br>
            • "C'est quoi le MMM ?"<br>
            • "Règles du segment Affluent ?"<br>
            • "PRO, MMM=90, VRD=3, age=40"<br>
            • "Pourquoi OR et pas AND ?"<br>
            • "C'est quoi un JDA ?"
        </div>""", unsafe_allow_html=True)

        st.markdown("---")
        if st.button("🗑️ Effacer conversation", use_container_width=True):
            st.session_state.messages = [{"role":"bot","content":"Conversation effacée. Comment puis-je vous aider ? 😊"}]
            st.session_state.nb_questions = 0
            st.rerun()

    # ── Onglets principaux ────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "🤖 BIATBot",
        "🔍 Simulation client",
        "🧪 Tests automatiques",
        "📋 Règles JSON"
    ])

    # ══ ONGLET 1 — CHATBOT ═══════════════════════════════════════
    with tab1:
        st.markdown("### Posez vos questions à BIATBot")
        st.caption("Le chatbot répond à 3 types de questions : Définitions · Règles de segmentation · Aide à la décision")

        # Affichage de l'historique
        chat_html = '<div class="chat-box">'
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                chat_html += f'<div class="msg-user"><div class="msg-nom-usr">Vous</div>{msg["content"]}</div>'
            else:
                contenu = msg["content"].replace("\n","<br>").replace("**","<strong>",1).replace("**","</strong>",1)
                chat_html += f'<div class="msg-bot"><div class="msg-nom-bot">🤖 BIATBot</div>{msg["content"]}</div>'
        chat_html += '</div>'
        st.markdown(chat_html, unsafe_allow_html=True)

        # Questions suggérées
        st.markdown("**💡 Questions rapides :**")
        c1,c2,c3,c4 = st.columns(4)
        suggestions = [
            ("C'est quoi le MMM ?",           "C'est quoi le MMM ?"),
            ("Règles du segment Affluent ?",   "Règles du segment Affluent ?"),
            ("Pourquoi OR pas AND ?",          "Pourquoi utiliser OR et pas AND dans la segmentation ?"),
            ("PRO MMM=90 VRD=3 age=40",       "Client PRO, MMM=90, VRD=3, age=40, profession=Commerçant"),
        ]
        for col,(lbl,q) in zip([c1,c2,c3,c4], suggestions):
            if col.button(lbl, key=f"btn_{lbl[:10]}", use_container_width=True):
                st.session_state.messages.append({"role":"user","content":q})
                reponse = generer_reponse_chatbot(q)
                st.session_state.messages.append({"role":"bot","content":reponse})
                st.session_state.nb_questions += 1
                st.rerun()

        # Zone de saisie
        st.markdown("---")
        with st.form("chat_form", clear_on_submit=True):
            ci,cb = st.columns([5,1])
            with ci:
                user_input = st.text_input(
                    "Votre question",
                    placeholder="Ex: Client PRO, MMM=90, VRD=3, age=40 → quel segment ?",
                    label_visibility="collapsed"
                )
            with cb:
                send = st.form_submit_button("📤 Envoyer", use_container_width=True)

        if send and user_input.strip():
            st.session_state.messages.append({"role":"user","content":user_input})
            reponse = generer_reponse_chatbot(user_input)
            st.session_state.messages.append({"role":"bot","content":reponse})
            st.session_state.nb_questions += 1
            st.rerun()

    # ══ ONGLET 2 — SIMULATION ════════════════════════════════════
    with tab2:
        st.markdown("### 🔍 Simuler le segment d'un client")
        st.caption("Entrez les données et obtenez le segment avec la justification complète")

        col1, col2 = st.columns(2, gap="large")

        with col1:
            st.markdown("#### Données client")
            marche    = st.selectbox("Marché",["PART","PRO","TRE","ENR"])
            forme_lbl = {"PART":"Particulier","PRO":"Professionnel","TRE":"TRE","ENR":"ENR"}
            st.caption(f"→ {forme_lbl[marche]}")
            age       = st.number_input("Âge (ans)", min_value=0, max_value=120, value=40)
            profs     = sorted(set(PROFESSIONS_POTENTIEL + PROFESSIONS_LIBERALES + [
                "Commerçant","Artisan","Fonctionnaire","Salarié","Étudiant","Retraité","Autre"
            ]))
            profession= st.selectbox("Profession", [p.capitalize() for p in profs])
            nationalite=st.selectbox("Nationalité",["Tunisienne","Autre"])
            residence  =st.selectbox("Résidence",  ["Oui","Non"])

        with col2:
            st.markdown("#### Données financières")
            st.info("**mD** = milliers de Dinars · Ex : 3 mD = 3 000 DT\n\n⚠️ La condition entre MMM et VRD est un **OU** (pas AND)")
            mmm    = st.number_input("MMM — Mouvements Mensuels Moyens (mD)", 0.0, 99999.0, 3.0, 0.5)
            vrd    = st.number_input("VRD — Total Avoirs Stables (mD)",        0.0, 99999.0, 50.0, 5.0)
            nb_ops = st.number_input("Nb opérations (12 mois)", 0, 9999, 24, 1,
                                      help="0 = compte dormant, détecté automatiquement")
            if nb_ops == 0:
                st.error("⚠️ Compte dormant détecté automatiquement")
            else:
                st.success(f"✅ Compte actif ({nb_ops} opérations)")

        st.markdown("---")
        _, btn_col, _ = st.columns([1,2,1])
        with btn_col:
            simuler = st.button("🚀 Calculer le segment", type="primary", use_container_width=True)

        if simuler:
            client = {
                "marche": marche, "age": age, "MMM": mmm, "VRD": vrd,
                "profession": profession, "nationalite": nationalite,
                "residence": residence, "nb_operations_12m": nb_ops
            }
            result = get_segment(client)

            if result.get("erreurs"):
                st.error("❌ Erreurs de validation :\n" + "\n".join(result["erreurs"]))
            else:
                seg   = result["segment"]
                sous  = result["sous_segment"]
                justif= result["justification"]

                ICONES = {
                    "Haut de Gamme":"🏆","Classe Moyenne":"🟢",
                    "Grand Public":"🔵","Les Jeunes":"🟣",
                    "TRE":"🌍","ENR":"🌐"
                }
                COULEURS = {
                    "Haut de Gamme":"#FEF9E7","Classe Moyenne":"#EAFAF1",
                    "Grand Public":"#EAF2FF","Les Jeunes":"#F5EEF8",
                    "TRE":"#FDEDEC","ENR":"#E8F8F5"
                }
                BORDERS = {
                    "Haut de Gamme":"#B8860B","Classe Moyenne":"#1B6B35",
                    "Grand Public":"#004080","Les Jeunes":"#6B21A8",
                    "TRE":"#C0392B","ENR":"#0F766E"
                }
                icone = ICONES.get(seg,"📊")
                bg    = COULEURS.get(seg,"#f5f5f5")
                bord  = BORDERS.get(seg,"#666")

                st.markdown(f"""
                <div style="background:{bg};border:2px solid {bord};border-bottom:4px solid {BIAT_ORANGE};
                            border-radius:12px;padding:20px;text-align:center;margin:14px 0;">
                    <div style="font-size:.9rem;color:{bord};margin-bottom:4px;">
                        Marché : {result['marche']}
                    </div>
                    <div style="font-size:2rem;font-weight:800;color:{bord};">{icone} {seg}</div>
                    <div style="font-size:1.05rem;color:{bord};margin-top:3px;">{sous}</div>
                </div>""", unsafe_allow_html=True)

                st.markdown("#### 📌 Justification")
                st.markdown(f"""
                <div style="background:{BIAT_GRAY};border-left:4px solid {BIAT_ORANGE};
                            border-radius:0 8px 8px 0;padding:10px 14px;font-size:.88rem;">
                    ✅ {justif}
                </div>""", unsafe_allow_html=True)

                # Résumé des valeurs clés
                c1,c2,c3 = st.columns(3)
                for col,(lbl,val) in zip([c1,c2,c3],[
                    ("MMM saisi",f"{mmm} mD"),
                    ("VRD saisi",f"{vrd} mD"),
                    ("Âge",f"{age} ans"),
                ]):
                    col.markdown(f'<div class="kpi-card"><div class="kpi-val" style="font-size:1.2rem;color:{bord};">{val}</div><div class="kpi-lbl">{lbl}</div></div>', unsafe_allow_html=True)

    # ══ ONGLET 3 — TESTS ════════════════════════════════════════
    with tab3:
        st.markdown("### 🧪 Tests automatiques de la logique de segmentation")
        st.caption("Vérification que la correction OR est bien appliquée")

        if st.button("▶️ Lancer tous les tests", type="primary", use_container_width=True):
            resultats = lancer_tests()
            nb_ok  = sum(1 for r in resultats if r["succes"])
            nb_tot = len(resultats)

            c1,c2,c3 = st.columns(3)
            c1.markdown(f'<div class="kpi-card"><div class="kpi-val">{nb_tot}</div><div class="kpi-lbl">Tests total</div></div>', unsafe_allow_html=True)
            c2.markdown(f'<div class="kpi-card"><div class="kpi-val" style="color:green;">{nb_ok}</div><div class="kpi-lbl">✅ Réussis</div></div>', unsafe_allow_html=True)
            c3.markdown(f'<div class="kpi-card"><div class="kpi-val" style="color:{"green" if nb_ok==nb_tot else "red"};">{nb_ok/nb_tot*100:.0f}%</div><div class="kpi-lbl">Taux de réussite</div></div>', unsafe_allow_html=True)

            st.markdown("---")
            for r in resultats:
                color = "#EAFAF1" if r["succes"] else "#FDEDEC"
                bord  = "#1B6B35" if r["succes"] else "#C0392B"
                st.markdown(f"""
                <div style="background:{color};border-left:4px solid {bord};
                            border-radius:0 8px 8px 0;padding:10px 14px;margin:6px 0;">
                    <strong>{r['emoji']} {r['description']}</strong><br>
                    <span style="font-size:.83rem;">
                        Attendu : <em>{r['attendu_segment']} — {r['attendu_sous_segment']}</em><br>
                        Obtenu  : <em>{r['obtenu_segment']} — {r['obtenu_sous_segment']}</em><br>
                        Justification : {r['justification']}
                    </span>
                </div>""", unsafe_allow_html=True)

    # ══ ONGLET 4 — RÈGLES JSON ═══════════════════════════════════
    with tab4:
        st.markdown("### 📋 Règles de segmentation en JSON")
        st.caption("Structure exportable et facilement modifiable — utilisée directement par le moteur de segmentation")

        choix = st.selectbox("Afficher les règles du marché", ["PART","PRO","TRE","ENR"])
        regles_marche = REGLES_SEGMENTATION_JSON["marches"].get(choix, {})
        st.json(regles_marche, expanded=True)

        # Export
        json_str = json.dumps(REGLES_SEGMENTATION_JSON, ensure_ascii=False, indent=2)
        st.download_button(
            "⬇️ Télécharger toutes les règles (JSON)",
            data=json_str,
            file_name="regles_segmentation_biat.json",
            mime="application/json",
            use_container_width=True
        )

    # ── Footer ────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="background:{BIAT_BLUE};color:rgba(255,255,255,.7);
                text-align:center;padding:12px;border-radius:10px;
                margin-top:24px;font-size:.76rem;
                border-top:3px solid {BIAT_ORANGE};">
        🤖 BIATBot — PFE Master 2 Business Analytics · BIAT — Note PBD N°2023-06
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
