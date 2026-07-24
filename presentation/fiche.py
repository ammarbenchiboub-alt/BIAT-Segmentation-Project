"""
FICHE DE DECISION — justificatif exportable d'une segmentation.

Produit un document HTML autonome (aucune ressource externe) restituant une
decision de segmentation et tout ce qui permet de la justifier a posteriori :
profil analyse, segment attribue, regle appliquee, conditions verifiees,
parcours d'evaluation, EMPREINTE DE LA VERSION DES REGLES, horodatage et
utilisateur.

Pourquoi un document
--------------------
En controle interne bancaire, une decision qui ne peut pas etre justifiee par
ecrit n'est pas opposable. Le journal d'audit garantit la tracabilite INTERNE ;
la fiche fournit le justificatif REMETTABLE (au client, a l'encadrant, a un
auditeur), archivable hors de l'application.

Choix technique : HTML autonome plutot que PDF
----------------------------------------------
Le format HTML avec feuille de style d'impression permet a l'utilisateur de
generer un PDF via son navigateur (Ctrl+P -> Enregistrer en PDF), SANS ajouter
de dependance au projet. Or requirements.txt est volontairement fige pour
garantir la reproductibilite (voir Note 06 du journal) : introduire une
bibliotheque PDF aurait alourdi l'environnement et cree un risque de
divergence, pour un benefice nul par rapport a l'impression navigateur.

Ce module ne DECIDE rien : il restitue un resultat deja calcule par le moteur
et une analyse deja produite par le paquet explicabilite. Fonction pure
(str en sortie), donc testable sans interface.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Any

from commun import en_dinars

# Champs du profil restitues, dans l'ordre de lecture metier.
_CHAMPS_PROFIL = [
    ("Marche", "Marche"),
    ("Profession", "Profession"),
    ("Age", "Age"),
    ("MMM", "MMM (mouvements mensuels moyens)"),
    ("VRD", "VRD (total des avoirs stables)"),
    ("Nationalite", "Nationalite"),
    ("Residence", "Residence"),
    ("EpargnantDeposantExclusif", "Epargnant / deposant exclusif"),
]

_MONETAIRES = {"MMM", "VRD"}


def _e(valeur: Any) -> str:
    return html.escape(str(valeur))


def _valeur_affichee(champ: str, valeur: Any) -> str:
    if valeur in (None, ""):
        return "—"
    if champ in _MONETAIRES:
        return f"{en_dinars(valeur)} DT"
    if champ == "EpargnantDeposantExclusif":
        return "Oui" if bool(valeur) else "Non"
    return str(valeur)


def _lignes_profil(profil: dict) -> str:
    lignes = []
    for cle, libelle in _CHAMPS_PROFIL:
        if cle not in profil:
            continue
        lignes.append(
            f"<tr><th>{_e(libelle)}</th><td>{_e(_valeur_affichee(cle, profil.get(cle)))}</td></tr>"
        )
    return "".join(lignes)


def generer_fiche_html(
    resultat: Any,
    utilisateur: dict | None = None,
    version_regles: str = "",
    etapes: list | None = None,
    ecarts: list | None = None,
    horodatage: str | None = None,
) -> str:
    """Construit la fiche de decision (document HTML autonome).

    Parametres
    ----------
    resultat        : ResultatSegmentation produit par le moteur.
    utilisateur     : {"identifiant", "nom", "role"} de l'agent ayant realise
                      la simulation (tracabilite : qui a decide).
    version_regles  : empreinte du fichier de regles au moment de la decision.
                      C'est ce qui permet de rejouer la decision des annees
                      plus tard, meme apres evolution des seuils.
    etapes / ecarts : sorties du paquet explicabilite (facultatives).
    horodatage      : date de la decision (UTC ISO). Genere si absent.
    """
    horodatage = horodatage or datetime.now(timezone.utc).isoformat(timespec="seconds")
    profil = dict(getattr(resultat, "profil", {}) or {})
    succes = bool(getattr(resultat, "succes", False))
    segment = getattr(resultat, "segment", None) or "Non segmente"
    sous_segment = getattr(resultat, "sous_segment", None) or "—"
    regle_id = getattr(resultat, "regle_id", None) or "—"
    message = getattr(resultat, "message", "") or ""
    utilisateur = utilisateur or {}

    # --- Conditions verifiees de la regle retenue -------------------------
    conditions = ""
    prefixe = f"[{regle_id}]"
    for ligne in getattr(resultat, "explications", []) or []:
        texte = str(ligne).strip()
        if texte.startswith(prefixe):
            contenu = texte.split("]", 1)[1].strip() if "]" in texte else texte
            conditions += f"<li>{_e(contenu)}</li>"
    bloc_conditions = (
        f"<h2>Conditions verifiees</h2><ul class='check'>{conditions}</ul>"
        if conditions else ""
    )

    # --- Parcours d'evaluation -------------------------------------------
    bloc_parcours = ""
    if etapes:
        lignes = "".join(
            f"<tr><td>{_e(e.priorite)}</td><td>{_e(e.segment)} / {_e(e.sous_segment)}</td>"
            f"<td>{_e(e.libelle_statut)}</td><td class='mono'>{_e(e.regle_id)}</td></tr>"
            for e in etapes
        )
        bloc_parcours = (
            "<h2>Parcours d'evaluation</h2>"
            "<p class='note'>Regles du marche evaluees par ordre de priorite. Le moteur "
            "retient la premiere regle satisfaite.</p>"
            "<table class='grille'><thead><tr><th>Priorite</th><th>Segment vise</th>"
            f"<th>Statut</th><th>Regle</th></tr></thead><tbody>{lignes}</tbody></table>"
        )

    # --- Ecarts vers un autre segment ------------------------------------
    bloc_ecarts = ""
    if ecarts:
        lignes = "".join(
            f"<tr><td>{_e(ec.variable)}</td>"
            f"<td>{_e(en_dinars(ec.valeur_actuelle))} DT</td>"
            f"<td>{_e(en_dinars(ec.seuil))} DT</td>"
            f"<td class='delta'>+ {_e(en_dinars(ec.delta))} DT</td>"
            f"<td>{_e(ec.segment)} / {_e(ec.sous_segment)}</td></tr>"
            for ec in ecarts
        )
        bloc_ecarts = (
            "<h2>Ecarts vers un autre segment</h2>"
            "<p class='note'>Montants a atteindre pour changer de segment. Chaque ligne a "
            "ete verifiee en soumettant le profil modifie au moteur de segmentation.</p>"
            "<table class='grille'><thead><tr><th>Variable</th><th>Valeur actuelle</th>"
            "<th>Seuil</th><th>Ecart</th><th>Segment obtenu</th></tr></thead>"
            f"<tbody>{lignes}</tbody></table>"
        )

    etat = "ok" if succes else "ko"
    entete_decision = (
        f"<div class='decision {etat}'>"
        f"<div class='kicker'>Segment attribue</div>"
        f"<div class='seg'>{_e(segment)}</div>"
        f"<div class='sous'>{_e(sous_segment)}</div>"
        f"<div class='regle'>Regle appliquee : {_e(regle_id)}</div></div>"
    )
    if not succes and message:
        entete_decision += f"<div class='alerte'>{_e(message)}</div>"

    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<title>Fiche de decision - {_e(segment)}</title>
<style>
*{{box-sizing:border-box;}}
body{{font-family:'Segoe UI',Arial,sans-serif;color:#1F2A3C;margin:0;padding:32px;
 background:#F5F7FA;line-height:1.5;}}
.page{{max-width:820px;margin:0 auto;background:#fff;padding:36px 40px;
 border-radius:14px;box-shadow:0 2px 14px rgba(0,80,143,.10);}}
header{{display:flex;align-items:baseline;gap:14px;border-bottom:3px solid #F59E0B;
 padding-bottom:14px;margin-bottom:8px;}}
header .marque{{font-size:1.5rem;font-weight:800;color:#00508F;letter-spacing:-.4px;}}
header .titre{{font-size:1.02rem;color:#5A6B85;}}
.meta{{font-size:.78rem;color:#5A6B85;margin-bottom:22px;}}
h2{{font-size:.95rem;color:#00508F;margin:26px 0 10px;padding-left:10px;
 border-left:4px solid #F59E0B;}}
.decision{{border-radius:12px;padding:20px 24px;color:#fff;margin:10px 0 4px;
 background:linear-gradient(135deg,#00508F,#00365F);}}
.decision.ko{{background:linear-gradient(135deg,#B23A3A,#7d2727);}}
.decision .kicker{{font-size:.68rem;text-transform:uppercase;letter-spacing:1.1px;opacity:.85;}}
.decision .seg{{font-size:1.6rem;font-weight:800;margin-top:2px;}}
.decision .sous{{font-size:1rem;opacity:.95;}}
.decision .regle{{font-size:.74rem;opacity:.8;margin-top:10px;font-family:Consolas,monospace;}}
.alerte{{background:#FEF4E4;border-left:4px solid #D97F06;padding:11px 14px;
 border-radius:8px;margin-top:10px;font-size:.88rem;}}
table{{width:100%;border-collapse:collapse;font-size:.86rem;}}
table th,table td{{text-align:left;padding:8px 10px;border-bottom:1px solid #E4E9F2;}}
table th{{color:#5A6B85;font-weight:600;width:38%;}}
.grille thead th{{background:#00508F;color:#fff;width:auto;font-weight:700;
 text-transform:uppercase;font-size:.7rem;letter-spacing:.4px;}}
.grille tbody tr:nth-child(even){{background:#F7F9FC;}}
.mono{{font-family:Consolas,monospace;font-size:.78rem;color:#5A6B85;}}
.delta{{font-weight:700;color:#00508F;}}
ul.check{{list-style:none;padding:0;margin:0;}}
ul.check li{{padding:6px 0 6px 26px;position:relative;font-size:.88rem;
 border-bottom:1px solid #F0F3F8;}}
ul.check li::before{{content:"✓";position:absolute;left:4px;color:#1E7F5C;font-weight:800;}}
.note{{font-size:.78rem;color:#5A6B85;margin:0 0 8px;}}
footer{{margin-top:30px;padding-top:14px;border-top:1px solid #E4E9F2;
 font-size:.72rem;color:#8A97AB;}}
footer .empreinte{{font-family:Consolas,monospace;}}
@media print{{
 body{{background:#fff;padding:0;}}
 .page{{box-shadow:none;border-radius:0;max-width:none;padding:0;}}
 h2{{page-break-after:avoid;}}
 table{{page-break-inside:avoid;}}
}}
</style></head><body><div class="page">
<header><div class="marque">BIAT</div>
<div class="titre">Fiche de decision — segmentation clientele PBD</div></header>
<div class="meta">Document genere le {_e(horodatage)} (UTC)
 &nbsp;·&nbsp; Agent : {_e(utilisateur.get('nom', '—'))}
 ({_e(utilisateur.get('identifiant', '—'))}, role {_e(utilisateur.get('role', '—'))})</div>
{entete_decision}
<h2>Profil analyse</h2>
<table><tbody>{_lignes_profil(profil)}</tbody></table>
{bloc_conditions}
{bloc_parcours}
{bloc_ecarts}
<footer>
Decision produite par le moteur unique de segmentation, en application de la
Note BIAT 2023-06. Version du referentiel de regles utilisee :
<span class="empreinte">{_e(version_regles or '—')}</span>.
Cette empreinte identifie de maniere unique le jeu de seuils en vigueur au
moment de la decision et permet de la rejouer a l'identique ulterieurement.
Chaque decision est par ailleurs enregistree dans le journal d'audit de
l'application.
</footer>
</div></body></html>"""
