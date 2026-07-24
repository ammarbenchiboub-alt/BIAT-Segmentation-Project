"""
Generation du rapport d'evaluation du modele ML (Markdown).

Le rapport est PRODUIT A PARTIR des mesures reelles (evaluation.mesures.evaluer) :
les chiffres qu'il contient sont donc toujours synchronises avec le code, jamais
saisis a la main. Pour regenerer le rapport :

    python -m evaluation.rapport
"""
from __future__ import annotations

import os
from datetime import datetime

from .jeu_reference import TYPES_ANOMALIES
from .mesures import evaluer

_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHEMIN_RAPPORT = os.path.join(_RACINE, "docs", "EVALUATION_ML.md")


def _pct(x: float) -> str:
    return f"{x * 100:.1f} %".replace(".", ",")


def _f3(x: float) -> str:
    return f"{x:.3f}".replace(".", ",")


def generer_rapport_markdown(resultats: dict | None = None) -> str:
    r = resultats or evaluer()
    i, b = r["isolation_forest"], r["baseline"]
    horodatage = datetime.now().strftime("%Y-%m-%d")

    lignes = []
    A = lignes.append

    A(f"# Evaluation du modele de detection d'anomalies (Isolation Forest)\n")
    A(f"> Rapport genere automatiquement le {horodatage} par `python -m evaluation.rapport`.")
    A(f"> Chiffres issus directement des mesures (`evaluation.mesures.evaluer`), sur le modele livre.\n")

    A("## 1. Objet\n")
    A("Ce rapport evalue rigoureusement le module de detection d'anomalies "
      "(Isolation Forest), afin de justifier son emploi. Le modele **n'est pas "
      "modifie** : il est charge tel quel et note sur un jeu de reference "
      "etiquete. Le module de detection reste **complementaire** au moteur de "
      "segmentation, qu'il ne remplace ni ne modifie jamais.\n")

    A("## 2. Methodologie\n")
    A("Le modele est non supervise et entraine sur des donnees **simulees** : il "
      "n'existe donc aucune anomalie de reference « naturelle ». On construit un "
      "jeu d'evaluation **etiquete** et reproductible :\n")
    A(f"- **{r['n_normaux']} profils normaux** tenus a l'ecart : meme distribution "
      "que l'entrainement mais **graine differente** (aucune fuite) ;")
    A(f"- **{r['n_anomalies']} anomalies injectees**, etiquetees par type, chacune "
      "representant une erreur de saisie ou une combinaison implausible.\n")
    A("Familles d'anomalies :\n")
    for cle, desc in TYPES_ANOMALIES.items():
        A(f"- **{cle}** : {desc}")
    A("\n> Limite methodologique assumee : l'evaluation mesure la capacite du "
      "modele a retrouver des anomalies **connues et injectees**, selon la "
      "definition ci-dessus. Les donnees d'entrainement etant simulees, les "
      "resultats sont conditionnels a ces hypotheses. C'est la demarche standard "
      "en detection non supervisee faute de labels reels.\n")

    A("## 3. Resultats globaux\n")
    A("| Metrique | Isolation Forest | Baseline (regles simples) |")
    A("|---|---|---|")
    A(f"| ROC-AUC (classement) | **{_f3(i['roc_auc'])}** | {_f3(b['roc_auc'])} |")
    A(f"| PR-AUC | {_f3(i['pr_auc'])} | {_f3(b['pr_auc'])} |")
    A(f"| Precision (au seuil) | {_f3(i['precision'])} | {_f3(b['precision'])} |")
    A(f"| Rappel (au seuil) | {_f3(i['rappel'])} | {_f3(b['rappel'])} |")
    A(f"| F1 (au seuil) | {_f3(i['f1'])} | {_f3(b['f1'])} |")
    A(f"| **Fausses alertes sur clients normaux** | **{_pct(i['fausses_alertes_normaux'])}** "
      f"| {_pct(b['fausses_alertes_normaux'])} |")
    A("")
    A("La baseline est un detecteur transparent (z-score robuste par marche sur "
      "MMM/VRD + bornes d'age), representant « ce qu'on obtiendrait avec quelques "
      "regles simples ».\n")

    A("### Lecture\n")
    A(f"- **Discrimination** : l'Isolation Forest classe nettement mieux les "
      f"anomalies (ROC-AUC {_f3(i['roc_auc'])} contre {_f3(b['roc_auc'])} pour la "
      "baseline).")
    A(f"- **Fausses alertes, le point decisif** : au seuil de production, la "
      f"baseline signale **{_pct(b['fausses_alertes_normaux'])}** des clients "
      f"NORMAUX a tort — inexploitable en agence. L'Isolation Forest se limite a "
      f"**{_pct(i['fausses_alertes_normaux'])}**. La baseline n'atteint son rappel "
      "eleve qu'au prix d'un deluge de fausses alertes.")
    A(f"- **Rappel modere ({_f3(i['rappel'])}) au seuil actuel** : le modele est "
      "volontairement conservateur (peu de fausses alertes). La courbe "
      "operationnelle (section 5) montre qu'on peut le rendre plus sensible si on "
      "accepte davantage de fausses alertes.\n")

    A("## 4. Interpretation de `contamination = 0.06`\n")
    A(f"Mesure : le modele signale **{_pct(i['fausses_alertes_normaux'])}** des "
      "profils normaux — soit tres exactement l'ordre de grandeur de "
      "`contamination = 0.06`. Ce parametre n'est donc **pas arbitraire** : il "
      "fixe le **budget de fausses alertes** accepte sur la clientele normale "
      "(~6 %). Le retenir a 6 % est un choix operationnel (volume d'alertes "
      "soutenable pour un conseiller), desormais **mesure et justifie**, et non "
      "plus un nombre pose sans raison.\n")

    A("## 5. Courbe operationnelle (justification du seuil)\n")
    A("Pour differents budgets de fausses alertes (seuil fixe sur la distribution "
      "des scores des clients normaux), rappel obtenu sur les anomalies :\n")
    A("| Budget de fausses alertes | Rappel des anomalies |")
    A("|---|---|")
    for pt in r["courbe_operationnelle"]:
        marque = " *(reglage actuel)*" if abs(pt["budget_fausses_alertes"] - 0.06) < 1e-9 else ""
        A(f"| {_pct(pt['budget_fausses_alertes'])}{marque} | {_f3(pt['rappel'])} |")
    A("")
    A("Lecture : augmenter le budget accroit le rappel, au prix de plus de "
      "fausses alertes. Le reglage a 6 % privilegie la sobriete des alertes ; un "
      "reglage plus eleve serait justifiable si l'on souhaitait detecter "
      "davantage d'anomalies. Ce compromis est desormais **explicite et "
      "quantifie**.\n")

    A("## 6. Forces et faiblesses par type d'anomalie\n")
    A("| Type d'anomalie | Rappel Isolation Forest | Rappel Baseline |")
    A("|---|---|---|")
    for type_ in r["rappel_par_type_if"]:
        A(f"| {type_} | {_pct(r['rappel_par_type_if'][type_])} "
          f"| {_pct(r['rappel_par_type_baseline'][type_])} |")
    A("")
    A("- **Montants extremes** : parfaitement detectes par les deux methodes.")
    A("- **Age / profession incoherents** : bien captes par une regle d'age "
      "explicite (baseline) ; le modele, plus conservateur, en detecte une "
      "partie seulement.")
    A("- **Incoherence purement categorielle** (nationalite / residence "
      "contradictoires, montants normaux) : **faiblesse commune**. Un seul champ "
      "categoriel errone parmi sept se dilue dans le score d'isolement. Ni le "
      "modele ni des regles de montant ne traitent bien ce cas.\n")

    A("## 7. Le modele apporte-t-il une valeur reelle vs les regles ?\n")
    A("**Oui, une valeur mesurable, mais ciblee — pas un remplacement des "
      "regles.**\n")
    A("- Le moteur de segmentation **classe** ; il ne detecte pas les saisies "
      "incoherentes (il segmenterait sans broncher un client de 10 ans sur PRO). "
      "Le modele fournit ce filet de securite.")
    A(f"- Face a une baseline naive, l'Isolation Forest apporte un gain **decisif "
      f"sur le controle des fausses alertes** ({_pct(i['fausses_alertes_normaux'])} "
      f"contre {_pct(b['fausses_alertes_normaux'])}) et une **meilleure "
      "discrimination globale** — ce qui le rend, lui, exploitable en agence.")
    A("- **Mais** il ne dispense pas de **regles de validation ciblees** pour les "
      "incoherences categorielles, ou il est faible. La conclusion mature est "
      "un usage **hybride** : regles simples pour les controles evidents (age, "
      "coherence marche/residence), modele statistique pour les anomalies "
      "multivariees et le controle du volume d'alertes.\n")

    A("## 8. Limites restantes\n")
    A("- **Donnees d'entrainement simulees** : le modele apprend une distribution "
      "plausible, pas le comportement reel de clients BIAT. A rejouer sur "
      "historique reel des qu'il sera disponible.")
    A("- **Anomalies d'evaluation injectees** : la definition d'« anomalie » est "
      "celle de la section 2 ; d'autres definitions donneraient d'autres chiffres.")
    A("- **Faiblesse categorielle** documentee (section 6).")
    A("- **Rappel modere** au reglage actuel, par choix de sobriete des alertes "
      "(section 5).\n")

    A("## 9. Reproductibilite\n")
    A("Tout est deterministe (graines fixees). Pour rejouer :\n")
    A("```bash")
    A("python -m evaluation.rapport        # regenere ce rapport")
    A("python tests/test_ml_evaluation.py  # verrouille les metriques")
    A("```\n")
    A("Les metriques ci-dessus sont verrouillees par la suite "
      "`tests/test_ml_evaluation.py` : toute degradation notable du modele "
      "ferait echouer les tests.\n")

    return "\n".join(lignes)


def ecrire_rapport() -> str:
    contenu = generer_rapport_markdown()
    os.makedirs(os.path.dirname(CHEMIN_RAPPORT), exist_ok=True)
    with open(CHEMIN_RAPPORT, "w", encoding="utf-8") as f:
        f.write(contenu)
    return CHEMIN_RAPPORT


if __name__ == "__main__":
    chemin = ecrire_rapport()
    print(f"Rapport ecrit : {chemin}")
