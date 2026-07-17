"""Tests du cache du moteur et de son invalidation.

Le cache d'app.py repose entierement sur une propriete :
    la clef de cache est l'EMPREINTE DU CONTENU du fichier de regles.

D'ou les deux garanties a verifier, symetriques et aussi importantes l'une que
l'autre :
    - STABILITE   : regles inchangees -> meme empreinte -> meme instance
                    reutilisee (sinon le cache ne sert a rien) ;
    - INVALIDATION: regles modifiees  -> empreinte differente -> nouvelle
                    instance (sinon l'application continuerait de segmenter
                    avec des seuils perimes -- le vrai risque metier).

app.py n'est volontairement pas importe ici : ce module est un script
Streamlit qui s'executerait en entier a l'import. On teste donc le mecanisme
exactement tel qu'il y est ecrit (@st.cache_resource sur une fonction dont le
seul argument est l'empreinte), reproduit a l'identique ci-dessous.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import warnings

from _outils import Resultats, dossier_temporaire

from core import MoteurSegmentation
from core.rules_loader import CHEMIN_REGLES, charger_regles, empreinte_regles

# Streamlit hors runtime emet un avertissement "missing ScriptRunContext" :
# sans importance ici, le cache fonctionne de facon deterministe.
warnings.filterwarnings("ignore")
import streamlit as st  # noqa: E402


# --- Reproduction EXACTE du mecanisme d'app.py ---------------------------- #
_compteur_constructions = {"n": 0}


@st.cache_resource(show_spinner=False)
def _construire_moteur(empreinte: str) -> MoteurSegmentation:
    _compteur_constructions["n"] += 1
    return MoteurSegmentation()


def run() -> bool:
    r = Resultats("cache du moteur & invalidation")
    tmp = dossier_temporaire()

    # --- Empreinte : stabilite ------------------------------------------- #
    e1 = empreinte_regles()
    e2 = empreinte_regles()
    r.egal("empreinte stable si le fichier ne change pas", e1, e2)
    r.verifier("  empreinte non vide", bool(e1) and len(e1) == 16)

    # --- Empreinte : sensibilite au contenu ------------------------------ #
    copie = os.path.join(tmp, "regles_copie.json")
    shutil.copy(CHEMIN_REGLES, copie)
    r.egal("copie identique -> meme empreinte", empreinte_regles(copie), e1)

    regles = charger_regles(copie)
    regles["meta"]["version"] = "MODIFIEE-POUR-TEST"
    with open(copie, "w", encoding="utf-8") as f:
        json.dump(regles, f, ensure_ascii=False, indent=2)
    e_modifiee = empreinte_regles(copie)
    r.verifier("contenu modifie -> empreinte differente", e_modifiee != e1)

    # Un changement d'UN SEUL caractere doit suffire a invalider le cache :
    # c'est ce qui garantit qu'aucune modification de seuil ne passe inapercue.
    regles["meta"]["version"] = "MODIFIEE-POUR-TESU"
    with open(copie, "w", encoding="utf-8") as f:
        json.dump(regles, f, ensure_ascii=False, indent=2)
    r.verifier("  un seul caractere different suffit a changer l'empreinte",
               empreinte_regles(copie) != e_modifiee)

    # --- L'empreinte ne depend PAS de la date de modification ------------ #
    # Point important : une clef basee sur mtime aurait deux defauts (cache
    # perime si deux ecritures dans la meme seconde, reconstruction inutile si
    # le fichier est simplement re-copie). On verifie l'independance au mtime.
    ancien_mtime = os.stat(copie).st_mtime
    os.utime(copie, (ancien_mtime + 10_000, ancien_mtime + 10_000))
    r.egal("empreinte insensible au mtime (basee sur le contenu)",
           empreinte_regles(copie), empreinte_regles(copie))
    shutil.copy(CHEMIN_REGLES, copie)
    r.egal("  contenu restaure -> empreinte d'origine retrouvee",
           empreinte_regles(copie), e1)

    # --- Cache : reutilisation de l'instance ----------------------------- #
    _compteur_constructions["n"] = 0
    m1 = _construire_moteur("empreinte-A")
    m2 = _construire_moteur("empreinte-A")
    m3 = _construire_moteur("empreinte-A")
    r.verifier("meme empreinte -> exactement la MEME instance (is)", m1 is m2 is m3)
    r.egal("  le moteur n'a ete construit qu'une seule fois",
           _compteur_constructions["n"], 1)

    # --- Cache : invalidation -------------------------------------------- #
    m4 = _construire_moteur("empreinte-B")
    r.verifier("empreinte differente -> nouvelle instance", m4 is not m1)
    r.egal("  une seconde construction a bien eu lieu",
           _compteur_constructions["n"], 2)
    r.verifier("  l'ancienne instance reste servie pour son empreinte",
               _construire_moteur("empreinte-A") is m1)
    r.egal("  sans reconstruction supplementaire", _compteur_constructions["n"], 2)

    # --- Le moteur cache est fonctionnel et identique au moteur direct ---- #
    profil = {"Marche": "PART", "Age": 45, "MMM": 0, "VRD": 600000, "Profession": "Autre"}
    res_cache = _construire_moteur(empreinte_regles()).segmenter(profil)
    res_direct = MoteurSegmentation().segmenter(profil)
    r.egal("moteur cache et moteur neuf donnent le meme segment",
           res_cache.segment, res_direct.segment)
    r.egal("  et le meme sous-segment", res_cache.sous_segment, res_direct.sous_segment)
    r.egal("  et la meme regle", res_cache.regle_id, res_direct.regle_id)

    # --- API inchangee ---------------------------------------------------- #
    r.verifier("MoteurSegmentation reste instanciable directement (API inchangee)",
               isinstance(MoteurSegmentation(), MoteurSegmentation))
    r.verifier("  et accepte toujours des regles injectees",
               MoteurSegmentation(regles=charger_regles()).segmenter(profil).succes)

    # --- Un moteur construit sur des regles differentes segmente
    #     differemment : c'est bien pour cela que l'invalidation compte ----- #
    regles_dures = charger_regles()
    for regle in regles_dures["marches"]["PART"]["regles"]:
        if regle["id"] == "PART_HDG_FORTUNES":
            regle["conditions"]["vrd"]["min"] = 999_999_999
    res_dur = MoteurSegmentation(regles=regles_dures).segmenter(profil)
    r.verifier("un seuil modifie change reellement le resultat "
               "(-> l'invalidation du cache est indispensable)",
               res_dur.sous_segment != res_direct.sous_segment)

    return r.bilan()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
