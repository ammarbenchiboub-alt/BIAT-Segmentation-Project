"""
Theme visuel premium BIAT - identite visuelle officielle.

Palette : bleu BIAT (#00508F) + orange BIAT (#F59E0B), fonds blancs / gris
tres clair. Typographie "Inter" (moderne, tres lisible).

Le logo reel de la BIAT peut etre depose dans assets/logo_biat.png (ou .jpg,
.jpeg, .svg) : s'il est present, il est utilise automatiquement partout ou le
logo apparait (bandeau superieur, sidebar). En son absence, une icone SVG de
remplacement (memes couleurs / meme esprit graphique) est utilisee.

IMPORTANT : tout le HTML injecte via st.markdown est produit SANS indentation
en debut de ligne (Streamlit interprete un bloc indente comme du code).
Ce fichier ne contient AUCUNE logique metier : uniquement de la presentation.
"""
from __future__ import annotations

import base64
import os

import streamlit as st

# --------------------------------------------------------------------------- #
# Palette officielle BIAT
# --------------------------------------------------------------------------- #

BLEU = "#00508F"          # Bleu BIAT officiel
BLEU_FONCE = "#00365F"    # Variante foncee (degrades, sidebar)
BLEU_CLAIR = "#1E73B8"    # Variante claire (hover, accents)
ORANGE = "#F59E0B"        # Orange BIAT officiel
ORANGE_FONCE = "#D97F06"  # Variante foncee (hover boutons)
BLANC = "#FFFFFF"
FOND = "#F5F7FA"          # Gris tres clair (arriere-plan general)
FOND_CARTE = "#FFFFFF"
TEXTE = "#1F2A3C"
TEXTE_DOUX = "#5A6B85"
BORDURE = "#E4E9F2"

VERT_OK = "#1E7F5C"
VERT_OK_FOND = "#E3F4EC"
ROUGE_KO = "#B23A3A"
ROUGE_KO_FOND = "#FBE3E3"

COULEURS = {
    "Haut de Gamme": BLEU,
    "Premium": BLEU,
    "Classe Moyenne": VERT_OK,
    "Potentiel moyen": VERT_OK,
    "Grand Public": ORANGE_FONCE,
    "Faible potentiel": ORANGE_FONCE,
    "Les Jeunes": "#6A3FB5",
    "Inactif": "#8A8A8A",
    "-": "#8A8A8A",
}

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
_EXTENSIONS_LOGO = ("png", "jpg", "jpeg", "svg", "webp")


# --------------------------------------------------------------------------- #
# Logo (fichier reel si present, sinon icone de remplacement)
# --------------------------------------------------------------------------- #

def _chemin_logo_reel() -> str | None:
    for nom in ("logo_biat", "logo", "biat_logo"):
        for ext in _EXTENSIONS_LOGO:
            chemin = os.path.join(_ASSETS_DIR, f"{nom}.{ext}")
            if os.path.isfile(chemin):
                return chemin
    return None


def _logo_svg_remplacement() -> str:
    """Icone de remplacement (memes couleurs / meme esprit que le logo BIAT :
    carre bleu nuit avec un "elan" orange -> blanc en diagonale). Remplacee
    automatiquement des que assets/logo_biat.png (ou .jpg/.svg) est present."""
    return (
        '<svg width="46" height="46" viewBox="0 0 46 46" xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="46" height="46" rx="11" fill="{BLEU}"/>'
        '<defs><linearGradient id="biatGrad" x1="10" y1="34" x2="28" y2="10" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{ORANGE}"/><stop offset="1" stop-color="#FFD08A"/></linearGradient></defs>'
        '<path d="M13 32 L24 12 L29 19 L20 32 Z" fill="url(#biatGrad)"/>'
        '<path d="M24 32 L31 19 L35.5 25.5 L30.5 32 Z" fill="#FFFFFF" fill-opacity="0.95"/>'
        '</svg>'
    )


def logo_html(taille_px: int = 46) -> str:
    """Renvoie le HTML (balise <img> ou SVG inline) du logo a la taille demandee."""
    chemin = _chemin_logo_reel()
    if chemin:
        with open(chemin, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        ext = chemin.rsplit(".", 1)[-1].lower()
        mime = "image/svg+xml" if ext == "svg" else f"image/{'jpeg' if ext == 'jpg' else ext}"
        return (
            f'<img src="data:{mime};base64,{b64}" alt="BIAT" '
            f'style="height:{taille_px}px;width:auto;display:block;object-fit:contain;" />'
        )
    return _logo_svg_remplacement()


def logo_disponible() -> bool:
    return _chemin_logo_reel() is not None


# --------------------------------------------------------------------------- #
# CSS global
# --------------------------------------------------------------------------- #

def injecter_css() -> None:
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

    :root {{
        --biat-bleu: {BLEU};
        --biat-bleu-fonce: {BLEU_FONCE};
        --biat-bleu-clair: {BLEU_CLAIR};
        --biat-orange: {ORANGE};
        --biat-orange-fonce: {ORANGE_FONCE};
        --biat-fond: {FOND};
        --biat-texte: {TEXTE};
        --biat-texte-doux: {TEXTE_DOUX};
        --biat-bordure: {BORDURE};
    }}

    /* ============================== BASE ============================== */
    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
        color: var(--biat-texte);
    }}
    .stApp {{
        background: var(--biat-fond);
    }}
    .block-container {{
        padding-top: 2.6rem;
        padding-bottom: 3rem;
        max-width: 1300px;
    }}
    header[data-testid="stHeader"] {{
        background: var(--biat-fond);
    }}
    h1, h2, h3, h4 {{ color: var(--biat-bleu); font-weight: 800; letter-spacing: -.3px; }}
    a {{ color: var(--biat-bleu); }}

    @keyframes biatFadeUp {{
        from {{ opacity: 0; transform: translateY(8px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes biatFadeIn {{
        from {{ opacity: 0; }}
        to   {{ opacity: 1; }}
    }}

    /* ============================ SIDEBAR ============================== */
    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, var(--biat-bleu-fonce) 0%, var(--biat-bleu) 100%);
        border-right: none;
    }}
    section[data-testid="stSidebar"] > div {{ padding-top: 1.2rem; }}
    section[data-testid="stSidebar"] * {{ color: #EAF2FC !important; }}
    section[data-testid="stSidebar"] hr {{ border-color: rgba(255,255,255,.18); margin: 14px 0; }}

    .biat-sidebar-brand {{
        display: flex; align-items: center; gap: 10px;
        padding: 4px 6px 14px 6px;
        border-bottom: 1px solid rgba(255,255,255,.18);
        margin-bottom: 14px;
    }}
    .biat-sidebar-brand .brand-name {{ font-size: 1.05rem; font-weight: 800; letter-spacing: .3px; }}
    .biat-sidebar-brand .brand-sub {{ font-size: .68rem; opacity: .8; font-weight: 500; }}

    /* Navigation (st.radio detourne en menu) */
    section[data-testid="stSidebar"] div[role="radiogroup"] {{ gap: 4px; display: flex; flex-direction: column; }}
    section[data-testid="stSidebar"] div[role="radiogroup"] label {{
        padding: 10px 14px !important;
        border-radius: 11px !important;
        transition: background .18s ease, transform .12s ease;
        margin: 0 !important;
        cursor: pointer;
    }}
    section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
        background: rgba(255,255,255,.12);
        transform: translateX(2px);
    }}
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {{
        background: var(--biat-orange);
        box-shadow: 0 4px 14px rgba(245,158,11,.35);
    }}
    section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) * {{
        color: #1A1200 !important;
        font-weight: 700 !important;
    }}
    section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {{ display: none; }}
    section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] small {{
        opacity: .82; font-size: .72rem !important;
    }}

    /* ============================ MASTHEAD ============================= */
    .biat-masthead {{
        display: flex; align-items: center; gap: 18px;
        background: linear-gradient(120deg, var(--biat-bleu-fonce) 0%, var(--biat-bleu) 55%, var(--biat-bleu-clair) 100%);
        border-radius: 18px;
        padding: 20px 28px;
        margin-bottom: 22px;
        box-shadow: 0 10px 30px rgba(0,54,95,.22);
        position: relative;
        overflow: hidden;
        animation: biatFadeUp .45s ease;
    }}
    .biat-masthead::after {{
        content: "";
        position: absolute; right: -60px; top: -60px;
        width: 220px; height: 220px; border-radius: 50%;
        background: radial-gradient(circle, rgba(245,158,11,.28) 0%, rgba(245,158,11,0) 70%);
    }}
    .biat-masthead .masthead-logo {{ flex-shrink: 0; z-index: 1; }}
    .biat-masthead .masthead-text {{ z-index: 1; }}
    .biat-masthead .masthead-title {{
        color: #FFFFFF; font-size: 1.5rem; font-weight: 800; letter-spacing: -.3px; line-height: 1.2;
    }}
    .biat-masthead .masthead-sub {{
        color: #CFE0F2; font-size: .88rem; font-weight: 500; margin-top: 2px;
    }}
    .biat-masthead .masthead-badge {{
        margin-left: auto; z-index: 1;
        background: rgba(255,255,255,.14);
        border: 1px solid rgba(255,255,255,.28);
        color: #FFFFFF; padding: 7px 15px; border-radius: 999px;
        font-size: .74rem; font-weight: 700; white-space: nowrap;
        backdrop-filter: blur(2px);
    }}
    @media (max-width: 900px) {{
        .biat-masthead {{ flex-wrap: wrap; padding: 16px 20px; }}
        .biat-masthead .masthead-badge {{ margin-left: 0; }}
        .biat-masthead .masthead-title {{ font-size: 1.22rem; }}
    }}

    /* ============================ PAGE HEADER =========================== */
    .biat-header {{
        display: flex; align-items: center; gap: 16px; background: #FFFFFF;
        border: 1px solid var(--biat-bordure); border-left: 5px solid var(--biat-orange);
        border-radius: 14px; padding: 16px 22px; margin-bottom: 20px;
        box-shadow: 0 2px 12px rgba(0,80,143,.06);
        animation: biatFadeUp .4s ease;
    }}
    .biat-header h1 {{ font-size: 1.28rem; margin: 0; color: var(--biat-bleu); font-weight: 800; letter-spacing: -.2px; }}
    .biat-header p {{ margin: 3px 0 0; color: var(--biat-texte-doux); font-size: .86rem; }}
    .biat-header .chip {{
        margin-left: auto; background: #F1F5FB; color: var(--biat-bleu);
        border: 1px solid var(--biat-bordure); padding: 6px 13px; border-radius: 999px;
        font-size: .72rem; font-weight: 700; white-space: nowrap;
    }}

    /* ============================ SECTIONS ============================= */
    .section-title {{
        font-size: 1.02rem; font-weight: 700; color: var(--biat-bleu);
        margin: 22px 0 12px; padding-left: 11px; border-left: 4px solid var(--biat-orange);
        display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
    }}

    /* ============================ CARTES NAVIGABLES (Accueil) =========== */
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.nav-card-icon) {{
        border-radius: 16px !important; border: 1px solid var(--biat-bordure) !important;
        box-shadow: 0 2px 10px rgba(0,80,143,.06);
        transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
        animation: biatFadeUp .4s ease;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.nav-card-icon):hover {{
        transform: translateY(-3px);
        box-shadow: 0 12px 26px rgba(0,80,143,.16);
        border-color: rgba(245,158,11,.4);
    }}
    .nav-card-icon {{
        font-size: 1.3rem; width: 40px; height: 40px; border-radius: 11px;
        background: linear-gradient(135deg, rgba(0,80,143,.10), rgba(245,158,11,.14));
        display: flex; align-items: center; justify-content: center; margin-bottom: 8px;
    }}

    /* ============================ KPI CARDS ============================= */
    .kpi-card {{
        background: #FFFFFF; border: 1px solid var(--biat-bordure); border-radius: 16px;
        padding: 18px 20px; height: 100%;
        box-shadow: 0 2px 10px rgba(0,80,143,.06);
        transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
        animation: biatFadeUp .4s ease;
        position: relative; overflow: hidden;
    }}
    .kpi-card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 12px 26px rgba(0,80,143,.16);
        border-color: rgba(245,158,11,.4);
    }}
    .kpi-card .kpi-top {{ display: flex; align-items: center; justify-content: space-between; }}
    .kpi-card .kpi-icon {{
        font-size: 1.25rem; width: 38px; height: 38px; border-radius: 11px;
        background: linear-gradient(135deg, rgba(0,80,143,.10), rgba(245,158,11,.14));
        display: flex; align-items: center; justify-content: center;
    }}
    .kpi-label {{ font-size: .72rem; color: var(--biat-texte-doux); text-transform: uppercase; letter-spacing: .6px; font-weight: 700; margin-top: 10px; }}
    .kpi-value {{ font-size: 1.7rem; font-weight: 800; color: var(--biat-bleu); margin-top: 3px; line-height: 1.15; }}
    .kpi-hint {{ font-size: .75rem; color: #8A97AB; margin-top: 4px; }}

    /* ============================ SEGMENT CARD ========================== */
    .seg-card {{
        border-radius: 18px; padding: 26px 28px; color: #FFFFFF; margin: 4px 0 14px;
        box-shadow: 0 10px 28px rgba(0,80,143,.24); animation: biatFadeUp .45s ease;
        position: relative; overflow: hidden;
    }}
    .seg-card::after {{
        content: ""; position: absolute; right: -40px; bottom: -40px; width: 160px; height: 160px;
        border-radius: 50%; background: radial-gradient(circle, rgba(255,255,255,.10) 0%, rgba(255,255,255,0) 70%);
    }}
    .seg-card .seg-kicker {{ font-size: .72rem; text-transform: uppercase; letter-spacing: 1.2px; opacity: .85; font-weight: 700; }}
    .seg-card .seg-seg {{ font-size: 1.85rem; font-weight: 800; margin-top: 3px; }}
    .seg-card .seg-sous {{ font-size: 1.1rem; opacity: .96; margin-top: 3px; }}
    .seg-card .seg-rule {{ font-size: .76rem; opacity: .82; margin-top: 12px; font-family: 'JetBrains Mono', monospace; }}

    /* ============================ BADGES ================================ */
    .badge {{ display: inline-block; padding: 4px 12px; border-radius: 999px; font-size: .74rem; font-weight: 700; }}
    .badge-ok {{ background: {VERT_OK_FOND}; color: {VERT_OK}; }}
    .badge-warn {{ background: #FCEFD6; color: var(--biat-orange-fonce); }}
    .badge-bad {{ background: {ROUGE_KO_FOND}; color: {ROUGE_KO}; }}

    .legende {{ display: flex; flex-wrap: wrap; gap: 10px 16px; margin: 4px 0 8px; }}
    .legende .item {{ display: flex; align-items: center; gap: 7px; font-size: .8rem; color: var(--biat-texte-doux); font-weight: 500; }}
    .legende .dot {{ width: 11px; height: 11px; border-radius: 4px; display: inline-block; }}

    /* ============================ BOUTONS =============================== */
    div[data-testid="stButton"] button,
    div[data-testid="stFormSubmitButton"] button,
    div[data-testid="stDownloadButton"] button {{
        background: linear-gradient(135deg, var(--biat-bleu) 0%, var(--biat-bleu-clair) 100%);
        color: #fff; border: none; border-radius: 11px; padding: .55rem 1.3rem;
        font-weight: 700; letter-spacing: .2px;
        box-shadow: 0 3px 10px rgba(0,80,143,.22);
        transition: background .18s ease, transform .12s ease, box-shadow .18s ease;
    }}
    div[data-testid="stButton"] button:hover,
    div[data-testid="stFormSubmitButton"] button:hover,
    div[data-testid="stDownloadButton"] button:hover {{
        background: linear-gradient(135deg, var(--biat-orange-fonce) 0%, var(--biat-orange) 100%);
        transform: translateY(-1px);
        box-shadow: 0 8px 18px rgba(245,158,11,.32);
        color: #1A1200;
    }}
    div[data-testid="stButton"] button:active,
    div[data-testid="stFormSubmitButton"] button:active,
    div[data-testid="stDownloadButton"] button:active {{ transform: translateY(0); }}

    /* ============================ FORMULAIRES =========================== */
    div[data-testid="stForm"] {{
        background: #FFFFFF; border: 1px solid var(--biat-bordure); border-radius: 16px;
        padding: 22px 24px 12px; box-shadow: 0 2px 10px rgba(0,80,143,.05);
    }}
    label, .stMarkdown p {{ color: var(--biat-texte); }}
    div[data-testid="stWidgetLabel"] p {{ font-weight: 600 !important; font-size: .85rem !important; color: var(--biat-texte) !important; }}

    div[data-baseweb="select"] > div,
    .stNumberInput input, .stTextInput input, .stTextArea textarea {{
        border-radius: 10px !important; border: 1px solid var(--biat-bordure) !important;
        background: #FBFCFE !important; transition: border-color .15s ease, box-shadow .15s ease;
    }}
    div[data-baseweb="select"] > div:hover,
    .stNumberInput input:hover, .stTextInput input:hover {{ border-color: var(--biat-bleu-clair) !important; }}
    div[data-baseweb="select"]:focus-within > div,
    .stNumberInput input:focus, .stTextInput input:focus, .stTextArea textarea:focus {{
        border-color: var(--biat-orange) !important;
        box-shadow: 0 0 0 3px rgba(245,158,11,.18) !important;
    }}

    .stCheckbox label, .stRadio label {{ font-size: .88rem; }}
    div[data-testid="stCheckbox"] label span[data-baseweb="checkbox"] > div:first-child {{ border-radius: 6px !important; }}

    /* Radio "cartes" hors sidebar (formulaires) */
    div[data-testid="stForm"] div[role="radiogroup"] label,
    .main div[role="radiogroup"] label {{
        border: 1px solid var(--biat-bordure); border-radius: 10px; padding: 8px 14px !important;
        transition: border-color .15s ease, background .15s ease;
    }}
    .main div[role="radiogroup"] label:has(input:checked) {{
        border-color: var(--biat-orange); background: #FFF7EA;
    }}

    /* ============================ TABS =================================== */
    .stTabs [data-baseweb="tab-list"] {{ gap: 6px; border-bottom: 1px solid var(--biat-bordure); }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 10px 10px 0 0; padding: 10px 18px; font-weight: 600; color: var(--biat-texte-doux);
    }}
    .stTabs [aria-selected="true"] {{
        color: var(--biat-bleu) !important; background: #FFFFFF;
        border-bottom: 3px solid var(--biat-orange) !important; font-weight: 800;
    }}

    /* ============================ EXPANDER ================================ */
    details[data-testid="stExpander"] {{
        border: 1px solid var(--biat-bordure) !important; border-radius: 13px !important;
        background: #FFFFFF; box-shadow: 0 1px 6px rgba(0,80,143,.05); overflow: hidden;
    }}
    details[data-testid="stExpander"] summary {{ font-weight: 600; padding: 10px 6px; }}
    details[data-testid="stExpander"] summary:hover {{ color: var(--biat-bleu); }}

    /* ============================ DATAFRAMES / TABLEAUX ==================== */
    div[data-testid="stDataFrame"], div[data-testid="stTable"] {{
        border-radius: 14px !important; overflow: hidden;
        border: 1px solid var(--biat-bordure) !important;
        box-shadow: 0 2px 10px rgba(0,80,143,.06);
    }}
    table {{ border-collapse: collapse; width: 100%; }}
    div[data-testid="stTable"] table thead th {{
        background: var(--biat-bleu) !important; color: #FFFFFF !important;
        text-transform: uppercase; font-size: .72rem; letter-spacing: .4px; font-weight: 700;
    }}
    div[data-testid="stTable"] table tbody tr:nth-child(even) {{ background: #F7F9FC; }}
    div[data-testid="stTable"] table tbody tr:hover {{ background: #FFF3E0; }}

    /* ============================ ALERTES ================================ */
    div[data-testid="stAlert"] {{
        border-radius: 12px !important; border: 1px solid transparent;
        box-shadow: 0 2px 8px rgba(0,0,0,.05); padding: 2px 4px;
        animation: biatFadeIn .3s ease;
    }}

    /* ============================ CHAT ==================================== */
    div[data-testid="stChatMessage"] {{
        border-radius: 14px; box-shadow: 0 2px 8px rgba(0,80,143,.06);
        border: 1px solid var(--biat-bordure); margin-bottom: 4px;
    }}

    /* ============================ SCROLLBAR =============================== */
    ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: #C7D3E3; border-radius: 6px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: var(--biat-bleu-clair); }}

    /* ============================ RESPONSIVE =============================== */
    @media (max-width: 1200px) {{
        .block-container {{ padding-left: 1.6rem; padding-right: 1.6rem; }}
        .kpi-value {{ font-size: 1.45rem; }}
    }}
    @media (max-width: 900px) {{
        .seg-card .seg-seg {{ font-size: 1.5rem; }}
        .biat-header h1 {{ font-size: 1.08rem; }}
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Composants
# --------------------------------------------------------------------------- #

def masthead(
    titre: str = "Simulateur Intelligent de Segmentation Clientele",
    sous_titre: str = "Banque Internationale Arabe de Tunisie",
    badge: str = "Note BIAT 2023-06",
) -> None:
    """Bandeau superieur premium, identique sur toutes les pages."""
    html = (
        f'<div class="biat-masthead">'
        f'<div class="masthead-logo">{logo_html(46)}</div>'
        f'<div class="masthead-text"><div class="masthead-title">{titre}</div>'
        f'<div class="masthead-sub">{sous_titre}</div></div>'
        f'<div class="masthead-badge">{badge}</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def sidebar_brand(nom: str = "BIAT", sous_titre: str = "Segmentation clientele PBD") -> None:
    html = (
        f'<div class="biat-sidebar-brand">{logo_html(34)}'
        f'<div><div class="brand-name">{nom}</div><div class="brand-sub">{sous_titre}</div></div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def entete_biat(titre: str, sous_titre: str = "", chip: str = "Note BIAT 2023-06") -> None:
    chip_html = f'<div class="chip">{chip}</div>' if chip else ""
    html = (
        f'<div class="biat-header">{logo_html(38)}'
        f'<div><h1>{titre}</h1><p>{sous_titre}</p></div>{chip_html}</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def section(titre: str) -> None:
    st.markdown(f'<div class="section-title">{titre}</div>', unsafe_allow_html=True)


def kpi(label: str, valeur, hint: str = "", icone: str = "") -> None:
    icone_html = f'<div class="kpi-top"><div class="kpi-icon">{icone}</div></div>' if icone else ""
    hint_html = f'<div class="kpi-hint">{hint}</div>' if hint else ""
    st.markdown(
        f'<div class="kpi-card">{icone_html}<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{valeur}</div>{hint_html}</div>',
        unsafe_allow_html=True,
    )


def carte_segment(segment: str, sous_segment: str, regle_id: str) -> None:
    couleur = COULEURS.get(segment, BLEU)
    html = (
        f'<div class="seg-card" style="background:linear-gradient(135deg,{couleur},{BLEU_FONCE});">'
        f'<div class="seg-kicker">Segment attribue</div>'
        f'<div class="seg-seg">{segment or "Non segmente"}</div>'
        f'<div class="seg-sous">{sous_segment or ""}</div>'
        f'<div class="seg-rule">Regle : {regle_id or "-"}</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def legende_segments(segments) -> None:
    items = "".join(
        f'<div class="item"><span class="dot" style="background:{COULEURS.get(s, BLEU)}"></span>{s}</div>'
        for s in segments
    )
    st.markdown(f'<div class="legende">{items}</div>', unsafe_allow_html=True)
