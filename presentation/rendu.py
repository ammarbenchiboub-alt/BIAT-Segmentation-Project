"""
SMART RESPONSE RENDERER — Rendu Streamlit (couche d'adaptation).

Traduit les blocs abstraits produits par `presentation.plan` en composants
Streamlit concrets. C'est la SEULE partie du moteur de rendu qui depend de
Streamlit ; toute la logique de choix des composants est, elle, dans plan.py
(pure et testable).

Reutilisation : le rendu s'appuie sur les composants et le theme existants
(`ui.kpi`, `ui.carte_segment`, `ui.section`, palette BIAT, classes `.badge`)
plutot que de reintroduire un style parallele. Les quelques composants nouveaux
(encadre, checklist, liste titree, pastilles, reference) sont stylises en
coherence avec la charte, dans un unique bloc CSS injecte une fois.

Extensibilite : l'association type de bloc -> fonction de rendu est un registre
(`_RENDU`). Ajouter un composant = ajouter un type de bloc dans plan.py et une
entree ici. Aucune autre partie du code n'est touchee.
"""
from __future__ import annotations

import html

import streamlit as st

from ui import carte_segment, kpi, section
from ui.styles import (
    BLEU, BLEU_CLAIR, ORANGE_FONCE, ROUGE_KO, VERT_OK,
)

from .plan import (
    Accordeon, Badges, Bloc, Callout, CarteDecision, Checklist, GroupeKPI,
    ListeStructuree, Reference, Texte, Titre, planifier_reponse,
)

# --------------------------------------------------------------------------- #
# CSS des composants propres au moteur de rendu
# --------------------------------------------------------------------------- #
_TONS = {
    # ton -> (bordure, fond, couleur icone/texte accent)
    "info": (BLEU_CLAIR, "#EEF5FC", BLEU),
    "succes": (VERT_OK, "#E9F6F0", VERT_OK),
    "attention": (ORANGE_FONCE, "#FEF4E4", ORANGE_FONCE),
    "danger": (ROUGE_KO, "#FBECEC", ROUGE_KO),
    "neutre": ("#C7D3E3", "#F4F7FB", "#5A6B85"),
}


def injecter_css_rendu() -> None:
    """Injecte (une fois par page) le style des composants du moteur de rendu."""
    if st.session_state.get("_css_rendu_injecte"):
        return
    st.session_state["_css_rendu_injecte"] = True
    st.markdown(
        """
<style>
.smart-callout{display:flex;gap:11px;align-items:flex-start;border-radius:13px;
 padding:14px 16px;margin:6px 0 10px;border:1px solid var(--biat-bordure);
 border-left-width:4px;line-height:1.5;font-size:.92rem;animation:biatFadeIn .3s ease;}
.smart-callout .ic{font-size:1.1rem;line-height:1.3;flex-shrink:0;}
.smart-liste{display:flex;flex-direction:column;gap:8px;margin:6px 0 10px;}
.smart-liste .row{background:#FFFFFF;border:1px solid var(--biat-bordure);
 border-left:4px solid var(--biat-orange);border-radius:12px;padding:11px 15px;
 box-shadow:0 1px 6px rgba(0,80,143,.05);animation:biatFadeUp .35s ease;}
.smart-liste .row .t{font-weight:700;color:var(--biat-bleu);font-size:.94rem;}
.smart-liste .row .d{color:var(--biat-texte-doux);font-size:.86rem;margin-top:2px;}
.smart-check{display:flex;flex-direction:column;gap:7px;background:#FFFFFF;
 border:1px solid var(--biat-bordure);border-radius:13px;padding:14px 16px;margin:6px 0 10px;
 box-shadow:0 1px 6px rgba(0,80,143,.05);}
.smart-check .item{display:flex;gap:10px;align-items:flex-start;font-size:.9rem;line-height:1.45;}
.smart-check .mk{flex-shrink:0;font-weight:800;width:20px;text-align:center;}
.smart-check .mk.ok{color:#1E7F5C;}
.smart-check .mk.no{color:#8A97AB;}
.smart-chips{display:flex;flex-wrap:wrap;gap:8px;margin:4px 0 12px;}
.smart-chip{display:inline-block;padding:5px 13px;border-radius:999px;font-size:.8rem;
 font-weight:600;border:1px solid var(--biat-bordure);background:#F4F7FB;color:#42536b;}
.smart-chip.bleu{background:#EAF2FC;border-color:#CBDDF3;color:var(--biat-bleu);}
.smart-ref{display:inline-flex;align-items:center;gap:7px;margin:2px 0 2px;
 font-size:.78rem;color:var(--biat-texte-doux);font-style:italic;}
.smart-ref .pin{font-style:normal;}
</style>
""",
        unsafe_allow_html=True,
    )


def _echap(t: str) -> str:
    return html.escape(str(t))


# --------------------------------------------------------------------------- #
# Rendu par type de bloc
# --------------------------------------------------------------------------- #
def _rendu_titre(b: Titre) -> None:
    section(_echap(b.texte))


def _rendu_texte(b: Texte) -> None:
    st.markdown(_echap(b.texte))


def _rendu_callout(b: Callout) -> None:
    bordure, fond, _ = _TONS.get(b.ton, _TONS["info"])
    icone = f'<span class="ic">{_echap(b.icone)}</span>' if b.icone else ""
    st.markdown(
        f'<div class="smart-callout" style="border-color:{bordure};'
        f'border-left-color:{bordure};background:{fond};">{icone}'
        f'<span>{_echap(b.texte)}</span></div>',
        unsafe_allow_html=True,
    )


def _rendu_carte_decision(b: CarteDecision) -> None:
    # Reutilise le composant existant : coherence visuelle avec la page
    # "Simulation individuelle".
    carte_segment(b.segment, b.sous_segment, b.regle_id)


def _rendu_groupe_kpi(b: GroupeKPI) -> None:
    if not b.items:
        return
    colonnes = st.columns(len(b.items))
    for col, item in zip(colonnes, b.items):
        with col:
            kpi(item.label, item.valeur, item.hint, icone=item.icone)


def _rendu_checklist(b: Checklist) -> None:
    if not b.items:
        return
    if b.titre:
        section(_echap(b.titre))
    lignes = "".join(
        f'<div class="item"><span class="mk {"ok" if it.ok else "no"}">'
        f'{"✓" if it.ok else "•"}</span><span>{_echap(it.texte)}</span></div>'
        for it in b.items
    )
    st.markdown(f'<div class="smart-check">{lignes}</div>', unsafe_allow_html=True)


def _rendu_liste(b: ListeStructuree) -> None:
    if b.titre:
        section(_echap(b.titre))
    lignes = "".join(
        f'<div class="row"><div class="t">{_echap(it.titre)}</div>'
        + (f'<div class="d">{_echap(it.detail)}</div>' if it.detail else "")
        + "</div>"
        for it in b.items
    )
    st.markdown(f'<div class="smart-liste">{lignes}</div>', unsafe_allow_html=True)


def _rendu_badges(b: Badges) -> None:
    if not b.items:
        return
    classe = "smart-chip bleu" if b.ton == "bleu" else "smart-chip"
    chips = "".join(f'<span class="{classe}">{_echap(x)}</span>' for x in b.items)
    st.markdown(f'<div class="smart-chips">{chips}</div>', unsafe_allow_html=True)


def _rendu_reference(b: Reference) -> None:
    st.markdown(
        f'<div class="smart-ref"><span class="pin">🔖</span>Source : {_echap(b.source)}</div>',
        unsafe_allow_html=True,
    )


def _rendu_accordeon(b: Accordeon) -> None:
    with st.expander(b.titre):
        for sous in b.blocs:
            _rendu_bloc(sous)


# Registre type de bloc -> fonction de rendu (extensible).
_RENDU = {
    Titre: _rendu_titre,
    Texte: _rendu_texte,
    Callout: _rendu_callout,
    CarteDecision: _rendu_carte_decision,
    GroupeKPI: _rendu_groupe_kpi,
    Checklist: _rendu_checklist,
    ListeStructuree: _rendu_liste,
    Badges: _rendu_badges,
    Reference: _rendu_reference,
    Accordeon: _rendu_accordeon,
}


def _rendu_bloc(bloc: Bloc) -> None:
    fonction = _RENDU.get(type(bloc))
    if fonction is not None:
        fonction(bloc)
    else:  # pragma: no cover - garde-fou pour un type non enregistre
        st.markdown(_echap(getattr(bloc, "texte", str(bloc))))


def afficher_reponse(rep: dict) -> None:
    """Point d'entree du rendu : affiche une reponse du chatbot avec le
    composant le plus adapte. Robuste : ne leve jamais et retombe sur un
    affichage texte si un bloc n'a pas de rendu enregistre."""
    injecter_css_rendu()
    for bloc in planifier_reponse(rep):
        _rendu_bloc(bloc)
