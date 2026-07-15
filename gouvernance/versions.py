"""
Versionnement du fichier de regles (config/regles_segmentation.json).

Chaque fois qu'un changement de seuils/professions est confirme (voir
workflow_seuils.py), une copie horodatee du fichier de regles resultant est
conservee dans config/versions/. Rien n'est jamais ecrase silencieusement :
on peut toujours consulter ou restaurer une version anterieure.

La restauration d'une version passee ne modifie JAMAIS directement le
fichier de regles : elle cree une nouvelle PROPOSITION (via
gouvernance.workflow_seuils.proposer), qui doit etre confirmee par un second
administrateur comme n'importe quel autre changement -- aucun raccourci ne
permet de contourner la double validation, y compris pour un retour en
arriere.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER_VERSIONS = os.path.join(_BASE_DIR, "config", "versions")
CHEMIN_MANIFESTE = os.path.join(DOSSIER_VERSIONS, "manifeste.json")


def _charger_manifeste() -> list[dict[str, Any]]:
    if not os.path.exists(CHEMIN_MANIFESTE):
        return []
    with open(CHEMIN_MANIFESTE, encoding="utf-8") as f:
        return json.load(f)


def _sauvegarder_manifeste(manifeste: list[dict[str, Any]]) -> None:
    os.makedirs(DOSSIER_VERSIONS, exist_ok=True)
    with open(CHEMIN_MANIFESTE, "w", encoding="utf-8") as f:
        json.dump(manifeste, f, ensure_ascii=False, indent=2)


def enregistrer_version(
    regles: dict,
    applique_par: dict[str, Any],
    description: str,
    proposition_id: int | None = None,
) -> str:
    """Sauvegarde un instantane horodate des regles devenues actives.
    Renvoie l'identifiant de version (nom de fichier)."""
    os.makedirs(DOSSIER_VERSIONS, exist_ok=True)
    horodatage = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffixe = f"_prop{proposition_id}" if proposition_id else "_initiale"
    version_id = f"regles_{horodatage}{suffixe}.json"
    chemin = os.path.join(DOSSIER_VERSIONS, version_id)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(regles, f, ensure_ascii=False, indent=2)

    manifeste = _charger_manifeste()
    manifeste.append({
        "version_id": version_id,
        "horodatage": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "applique_par": applique_par.get("identifiant", "?"),
        "nom_applique_par": applique_par.get("nom", "?"),
        "description": description,
        "proposition_id": proposition_id,
    })
    _sauvegarder_manifeste(manifeste)
    return version_id


def assurer_version_initiale(regles_actuelles: dict) -> None:
    """A appeler au premier acces a la page Parametrage : si aucune version
    n'existe encore (mise en place du versionnement sur un projet deja en
    cours), enregistre l'etat actuel comme version de reference, pour ne
    jamais partir d'un historique vide."""
    if not _charger_manifeste():
        enregistrer_version(
            regles_actuelles,
            {"identifiant": "systeme", "nom": "Systeme"},
            "Version initiale (etat du fichier au moment de la mise en place du versionnement).",
        )


def lister_versions(limite: int = 100) -> list[dict[str, Any]]:
    """Renvoie les versions les plus recentes en premier."""
    manifeste = _charger_manifeste()
    return list(reversed(manifeste))[:limite]


def charger_version(version_id: str) -> dict:
    """Charge le contenu JSON d'une version donnee (lecture seule)."""
    chemin = os.path.join(DOSSIER_VERSIONS, version_id)
    with open(chemin, encoding="utf-8") as f:
        return json.load(f)
