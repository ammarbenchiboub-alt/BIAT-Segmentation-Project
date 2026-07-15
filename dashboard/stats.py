"""Indicateurs du tableau de bord, calcules a partir de l'historique des segmentations."""
from __future__ import annotations

SEGMENTS_PREMIUM = {"Haut de Gamme", "Premium"}


def _fmt_pct(x: float) -> str:
    return f"{x:.1f} %".replace(".", ",")


def calculer_kpis(df) -> dict:
    """Retourne un jeu d'indicateurs coherents et bien nommes."""
    if df is None or df.empty:
        return {
            "total": 0, "segmentes": 0, "taux_segmentation": "0 %",
            "segment_dominant": "-", "part_dominant": "",
            "part_haut_gamme": "0 %", "confiance_moyenne": "-",
            "marche_principal": "-",
        }

    total = len(df)
    seg = int((df.get("Statut", "Segmente") == "Segmente").sum()) if "Statut" in df else total
    taux = 100 * seg / total if total else 0

    # Segment dominant
    if "Segment" in df and not df["Segment"].dropna().empty:
        vc = df["Segment"].replace("-", None).dropna().value_counts()
        if not vc.empty:
            segment_dominant = vc.index[0]
            part_dominant = _fmt_pct(100 * vc.iloc[0] / total)
        else:
            segment_dominant, part_dominant = "-", ""
    else:
        segment_dominant, part_dominant = "-", ""

    # Part Haut de Gamme / Premium (indicateur commercial)
    if "Segment" in df:
        n_hg = int(df["Segment"].isin(SEGMENTS_PREMIUM).sum())
        part_hg = _fmt_pct(100 * n_hg / total)
    else:
        part_hg = "0 %"

    # Confiance moyenne de l'assistant (si disponible)
    if "Confiance" in df and df["Confiance"].notna().any():
        conf = df["Confiance"].dropna().mean()
        confiance_moyenne = f"{conf:.0f} %"
    else:
        confiance_moyenne = "-"

    # Marche le plus represente
    marche_principal = df["Marche"].mode().iloc[0] if "Marche" in df and not df["Marche"].dropna().empty else "-"

    return {
        "total": total,
        "segmentes": seg,
        "taux_segmentation": _fmt_pct(taux),
        "segment_dominant": segment_dominant,
        "part_dominant": part_dominant,
        "part_haut_gamme": part_hg,
        "confiance_moyenne": confiance_moyenne,
        "marche_principal": marche_principal,
    }


def repartition(df, colonne: str):
    """DataFrame (valeur, Effectif) trie, pour les graphiques."""
    import pandas as pd
    if df is None or df.empty or colonne not in df:
        return pd.DataFrame(columns=[colonne, "Effectif"])
    s = df[colonne].fillna("-").value_counts().reset_index()
    s.columns = [colonne, "Effectif"]
    return s


def calculer_kpis_ml(df) -> dict:
    """Indicateurs du module Machine Learning (detection d'anomalies), s'ils
    sont disponibles dans l'historique (colonnes ML_Anomalie / ML_Confiance).

    Ce module est purement complementaire : ces KPIs ne portent que sur
    l'analyse de coherence statistique, jamais sur le segment lui-meme.
    """
    if df is None or df.empty or "ML_Anomalie" not in df or df["ML_Anomalie"].isna().all():
        return {"disponible": False}

    sous = df[df["ML_Anomalie"].notna()]
    total = len(sous)
    anomalies = int(sous["ML_Anomalie"].fillna(False).astype(bool).sum())
    taux = _fmt_pct(100 * anomalies / total) if total else "0 %"

    if "ML_Confiance" in sous and sous["ML_Confiance"].notna().any():
        conf = sous["ML_Confiance"].dropna().mean()
        confiance_moyenne = f"{conf:.0f} %"
    else:
        confiance_moyenne = "-"

    return {
        "disponible": True,
        "total": total,
        "anomalies": anomalies,
        "taux_anomalies": taux,
        "confiance_moyenne": confiance_moyenne,
    }


def repartition_scores_confiance(df, colonne: str = "ML_Confiance"):
    """Regroupe une colonne de scores de confiance (0-100) par tranche, pour
    affichage graphique (histogramme simplifie)."""
    import pandas as pd
    bornes = [-1, 40, 55, 70, 85, 101]
    etiquettes = ["0-40 %", "40-55 %", "55-70 %", "70-85 %", "85-100 %"]
    if df is None or df.empty or colonne not in df or df[colonne].dropna().empty:
        return pd.DataFrame({"Tranche": etiquettes, "Effectif": [0] * len(etiquettes)})
    tranche = pd.cut(df[colonne].dropna(), bins=bornes, labels=etiquettes)
    s = tranche.value_counts().reindex(etiquettes, fill_value=0).reset_index()
    s.columns = ["Tranche", "Effectif"]
    return s
