"""
Generation du rapport d'analyse de portefeuille (Markdown).

Rapport PRODUIT a partir de l'analyse reelle (analyse_portefeuille.analyser) :
les chiffres sont toujours synchronises avec le code. Pour le regenerer :

    python -m analyse_portefeuille.rapport
"""
from __future__ import annotations

import os
from datetime import datetime

from . import analyser_portefeuille
from .portefeuille import GRAINE_PORTEFEUILLE, MIX_MARCHE, N_DEFAUT

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHEMIN_RAPPORT = os.path.join(_RACINE, "docs", "ANALYSE_PORTEFEUILLE.md")


def _pct(x) -> str:
    return f"{x} %".replace(".", ",")


def generer_rapport_markdown(resultats: dict | None = None) -> str:
    r = resultats or analyser_portefeuille()
    horodatage = datetime.now().strftime("%Y-%m-%d")
    L = []
    A = L.append

    A("# Analyse de la structure du portefeuille client PBD\n")
    A(f"> Rapport genere automatiquement le {horodatage} par "
      "`python -m analyse_portefeuille.rapport`.\n")

    A("## Question metier\n")
    A("**Comment se structure le portefeuille de la clientele PBD, ou se concentre "
      "la valeur, et quels leviers commerciaux en decoulent ?**\n")

    A("## Avertissement sur les donnees\n")
    A(f"En l'absence de donnees clients reelles BIAT, l'analyse porte sur un "
      f"**portefeuille representatif simule** de {r['n_clients']} clients (graine "
      f"fixee = {GRAINE_PORTEFEUILLE}, reproductible), **segmente par le moteur "
      "officiel**. Les profils sont simules ; les **segments sont reels** (produits "
      "par le moteur applique a la Note BIAT 2023-06). Les hypotheses de generation "
      "(mix de marche, professions, montants) sont explicites dans le code "
      "(`analyse_portefeuille/portefeuille.py`). Ces chiffres illustrent une "
      "METHODE d'analyse ; ils devront etre rejoues sur donnees reelles.\n")
    A("Mix de marche suppose : " + ", ".join(f"{m} {int(p*100)} %" for m, p in MIX_MARCHE.items()) + ".\n")

    A("## 1. Repartition par segment\n")
    A("| Segment | Part du portefeuille |")
    A("|---|---|")
    for s, p in sorted(r["repartition_segment"].items(), key=lambda kv: -kv[1]):
        if s == "-":
            continue
        A(f"| {s} | {_pct(p)} |")
    A("")
    A(f"Lecture : le portefeuille forme une **pyramide** classique -- une base large "
      f"de clientele de masse (Grand Public / Faible potentiel : {_pct(r['part_masse'])}), "
      f"une classe intermediaire, et un sommet etroit de forte valeur "
      f"(Haut de Gamme / Premium : {_pct(r['part_valeur'])}).\n")

    A("## 2. Concentration des avoirs\n")
    A(f"- Le **decile superieur** des clients detient **{_pct(r['concentration_top10'])}** "
      f"des avoirs totaux ; le **top 20 %** en detient **{_pct(r['concentration_top20'])}**.")
    A(f"- **Indice de Gini** des avoirs : **{str(r['gini_avoirs']).replace('.', ',')}** "
      "(0 = egalite parfaite, 1 = concentration maximale).")
    A(f"- Nuance : les segments de valeur (Haut de Gamme / Premium, "
      f"{_pct(r['part_valeur'])} des clients) ne detiennent que "
      f"{_pct(r['part_avoirs_segments_valeur'])} des avoirs, car une partie de ces "
      "clients sont qualifies par leur **profession** (a potentiel) et non par leurs "
      "montants. La valeur commerciale (relation) et la valeur patrimoniale (encours) "
      "ne se recouvrent donc pas totalement -- distinction utile au pilotage.\n")

    A("## 3. Croisement marche x segment\n")
    croise = r["croise_marche_segment"]
    segments = sorted({s for m in croise.values() for s in m})
    A("| Marche | " + " | ".join(segments) + " |")
    A("|" + "---|" * (len(segments) + 1))
    for marche, ligne in croise.items():
        A(f"| {marche} | " + " | ".join(f"{ligne.get(s, 0):.0f} %" for s in segments) + " |")
    A("")
    lignes_marche = []
    for m, v in r["par_marche"].items():
        lignes_marche.append(f"**{m}** ({v['effectif']} clients) : dominante "
                             f"{v['segment_dominant']} ({_pct(v['part_dominant'])}), "
                             f"valeur {_pct(v['part_valeur'])}")
    A("Par marche : " + " ; ".join(lignes_marche) + ".\n")

    if r["taux_anomalies"] is not None:
        A("## 4. Qualite des donnees (module ML)\n")
        A(f"Le module de detection d'anomalies signale **{_pct(r['taux_anomalies'])}** de "
          "profils atypiques dans ce portefeuille -- indicateur de la part de saisies "
          "potentiellement incoherentes a controler (voir `docs/EVALUATION_ML.md` pour "
          "l'evaluation du modele).\n")

    A("## 5. Constats\n")
    for c in r["constats"]:
        A(f"- {c}")
    A("")

    A("## 6. Recommandations\n")
    A("Recommandations derivees des indicateurs ci-dessus (chaque point est "
      "declenche par un chiffre du portefeuille, non pose a priori) :\n")
    for i, reco in enumerate(r["recommandations"], start=1):
        A(f"{i}. {reco}")
    A("")

    A("## 7. Limites et suite\n")
    A("- **Donnees simulees** : a rejouer sur historique client reel des qu'il sera "
      "disponible ; les valeurs changeraient, la methode non.")
    A("- **Hypotheses de generation** explicites et discutables (mix de marche, "
      "professions) : elles conditionnent les chiffres, pas la demarche.")
    A("- L'analyse est **reproductible** (`python -m analyse_portefeuille.rapport`) et "
      "**verrouillee** par `tests/test_analyse_portefeuille.py`.\n")

    return "\n".join(L)


def ecrire_rapport() -> str:
    contenu = generer_rapport_markdown()
    os.makedirs(os.path.dirname(CHEMIN_RAPPORT), exist_ok=True)
    with open(CHEMIN_RAPPORT, "w", encoding="utf-8") as f:
        f.write(contenu)
    return CHEMIN_RAPPORT


if __name__ == "__main__":
    print("Rapport ecrit :", ecrire_rapport())
