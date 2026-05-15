"""
╔══════════════════════════════════════════════════════════════════════╗
║   SIMULATEUR DE SEGMENTATION CLIENTÈLE - BIAT  v5.0                ║
║   Interface aux couleurs officielles BIAT                           ║
║   Bleu marine #002B5C + Orange #F5A623 + Logo SVG                  ║
║   PART et PRO séparés · Dormants auto · PDF · Sensibilité           ║
║   Note PBD N°2023-06                                                ║
╚══════════════════════════════════════════════════════════════════════╝

Installation :
    pip install streamlit pandas plotly openpyxl mysql-connector-python

Lancement :
    streamlit run simulateur_biat_v5.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from io import BytesIO
import numpy as np
import random
import json
import base64
from datetime import datetime
if "chat" not in st.session_state:
    st.session_state["chat"] = [{"r": "bot", "m": "Bonjour ! 👋 Je suis **BIATBot**. Comment puis-je vous aider ?"}]

# ─────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BIAT — Simulateur Segmentation",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────
# LOGO BIAT EN SVG (fidèle au logo officiel)
# Fond bleu marine + texte BIAT blanc + barre orange
# ─────────────────────────────────────────────────────────────────────
LOGO_BIAT_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 70" width="180" height="56">
  <!-- Fond bleu marine -->
  <rect width="220" height="70" rx="6" fill="#002B5C"/>
  <!-- Barre orange en bas -->
  <rect y="56" width="220" height="14" rx="0 0 6 6" fill="#F5A623"/>
  <!-- Slash / diagonal blanc -->
  <polygon points="18,10 34,10 22,50 6,50" fill="white" opacity="0.95"/>
  <!-- Texte BIAT blanc -->
  <text x="44" y="42" font-family="Arial Black, Arial" font-weight="900"
        font-size="28" fill="white" letter-spacing="2">BIAT</text>
  <!-- Sous-texte orange -->
  <text x="6" y="66" font-family="Arial" font-size="7" fill="#002B5C"
        font-weight="600" letter-spacing="0.5">BANQUE INTERNATIONALE ARABE DE TUNISIE</text>
</svg>
"""

LOGO_B64 = base64.b64encode(LOGO_BIAT_SVG.encode()).decode()

# ─────────────────────────────────────────────────────────────────────
# COULEURS OFFICIELLES BIAT
# ─────────────────────────────────────────────────────────────────────
BIAT_BLUE       = "#002B5C"   # Bleu marine principal
BIAT_BLUE_MED   = "#004080"   # Bleu moyen
BIAT_BLUE_LIGHT = "#E8EEF6"   # Bleu très clair (fond)
BIAT_ORANGE     = "#F5A623"   # Orange / or
BIAT_ORANGE_L   = "#FFF3DC"   # Orange très clair
BIAT_WHITE      = "#FFFFFF"
BIAT_GRAY       = "#F4F6F9"   # Fond gris clair
BIAT_GRAY_DARK  = "#6B7280"
BIAT_TEXT       = "#1A2B4A"   # Texte principal

# Couleurs segments (dans la palette BIAT)
COLORS = {
    "Haut de Gamme" : "#B8860B",   # Or foncé
    "Classe Moyenne": "#1B6B35",   # Vert forêt
    "Grand Public"  : "#004080",   # Bleu BIAT
    "Les Jeunes"    : "#6B21A8",   # Violet
    "TRE"           : "#C0392B",   # Rouge
    "ENR"           : "#0F766E",   # Vert teal
    "Non classifié" : "#6B7280",
}
COLORS_LIGHT = {
    "Haut de Gamme" : "#FEF9E7",
    "Classe Moyenne": "#EAFAF1",
    "Grand Public"  : "#EAF2FF",
    "Les Jeunes"    : "#F5EEF8",
    "TRE"           : "#FDEDEC",
    "ENR"           : "#E8F8F5",
    "Non classifié" : "#F5F5F5",
}

# ─────────────────────────────────────────────────────────────────────
# CSS OFFICIEL BIAT
# ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    /* ── Variables globales BIAT ── */
    :root {{
        --biat-blue:       {BIAT_BLUE};
        --biat-blue-med:   {BIAT_BLUE_MED};
        --biat-blue-light: {BIAT_BLUE_LIGHT};
        --biat-orange:     {BIAT_ORANGE};
        --biat-orange-l:   {BIAT_ORANGE_L};
        --biat-gray:       {BIAT_GRAY};
        --biat-text:       {BIAT_TEXT};
    }}

    /* ── Fond général ── */
    .stApp {{ background-color: {BIAT_GRAY}; }}
    .stApp > header {{ background-color: {BIAT_BLUE} !important; }}

    /* ── Header BIAT ── */
    .biat-header {{
        background: {BIAT_BLUE};
        border-bottom: 4px solid {BIAT_ORANGE};
        padding: 0 0 0 0;
        margin-bottom: 24px;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 4px 24px rgba(0,43,92,0.18);
    }}
    .biat-header-top {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 16px 28px 14px;
    }}
    .biat-header-title {{
        color: white;
        font-size: 1.55rem;
        font-weight: 700;
        letter-spacing: 0.3px;
        margin: 0;
    }}
    .biat-header-sub {{
        color: rgba(255,255,255,0.75);
        font-size: 0.82rem;
        margin-top: 3px;
    }}
    .biat-header-bar {{
        background: {BIAT_ORANGE};
        height: 5px;
        width: 100%;
    }}
    .biat-version {{
        background: rgba(245,166,35,0.2);
        color: {BIAT_ORANGE};
        padding: 3px 12px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid {BIAT_ORANGE};
    }}

    /* ── Navigation tabs ── */
    .stTabs [data-baseweb="tab-list"] {{
        background: white;
        border-radius: 10px 10px 0 0;
        padding: 6px 8px 0;
        gap: 4px;
        border-bottom: 2px solid {BIAT_ORANGE};
        box-shadow: 0 2px 8px rgba(0,43,92,0.07);
    }}
    .stTabs [data-baseweb="tab"] {{
        background: {BIAT_GRAY};
        border-radius: 8px 8px 0 0;
        color: {BIAT_TEXT};
        font-weight: 600;
        font-size: 0.85rem;
        padding: 8px 18px;
        border: 1px solid #e2e8f0;
        border-bottom: none;
    }}
    .stTabs [aria-selected="true"] {{
        background: {BIAT_BLUE} !important;
        color: white !important;
        border-color: {BIAT_BLUE} !important;
    }}
    .stTabs [data-baseweb="tab-panel"] {{
        background: white;
        border-radius: 0 0 10px 10px;
        padding: 20px;
        box-shadow: 0 2px 8px rgba(0,43,92,0.07);
    }}

    /* ── Sidebar BIAT ── */
    [data-testid="stSidebar"] {{
        background: {BIAT_BLUE} !important;
    }}
    [data-testid="stSidebar"] * {{
        color: white !important;
    }}
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stNumberInput label,
    [data-testid="stSidebar"] .stSlider label {{
        color: rgba(255,255,255,0.85) !important;
        font-size: 0.8rem !important;
    }}
    [data-testid="stSidebar"] .stButton button {{
        background: {BIAT_ORANGE} !important;
        color: {BIAT_BLUE} !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 6px !important;
    }}
    [data-testid="stSidebar"] .stExpander {{
        background: rgba(255,255,255,0.08) !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 8px !important;
        margin-bottom: 6px;
    }}
    [data-testid="stSidebar"] .stExpander summary {{
        color: white !important;
        font-weight: 600 !important;
    }}

    /* ── Bouton principal ── */
    .stButton button[kind="primary"] {{
        background: {BIAT_BLUE} !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 10px 24px !important;
        font-size: 0.95rem !important;
        box-shadow: 0 2px 8px rgba(0,43,92,0.25) !important;
        transition: all 0.2s !important;
    }}
    .stButton button[kind="primary"]:hover {{
        background: {BIAT_ORANGE} !important;
        color: {BIAT_BLUE} !important;
    }}

    /* ── Cartes KPI ── */
    .kpi-card {{
        background: white;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
        border: 1px solid #e2e8f0;
        border-top: 3px solid {BIAT_ORANGE};
        box-shadow: 0 2px 8px rgba(0,43,92,0.07);
    }}
    .kpi-val {{ font-size: 2rem; font-weight: 700; line-height: 1.1; color: {BIAT_BLUE}; }}
    .kpi-lbl {{ font-size: 0.78rem; color: {BIAT_GRAY_DARK}; margin-top: 3px; }}
    .kpi-pct {{ font-size: 0.72rem; color: #aaa; }}

    /* ── Résultat simulation ── */
    .resultat-box {{
        border-radius: 12px; padding: 22px; margin: 14px 0;
        text-align: center;
        box-shadow: 0 4px 16px rgba(0,43,92,0.12);
        border-bottom: 4px solid {BIAT_ORANGE};
    }}
    .r-marche  {{ font-size: 0.9rem; font-weight: 500; opacity: 0.8; margin-bottom: 4px; }}
    .r-segment {{ font-size: 1.9rem; font-weight: 800; margin-bottom: 3px; }}
    .r-sous    {{ font-size: 1rem; opacity: 0.85; }}

    /* ── Règles appliquées ── */
    .regle-item {{
        background: {BIAT_ORANGE_L};
        border-left: 4px solid {BIAT_ORANGE};
        border-radius: 0 8px 8px 0;
        padding: 9px 14px; margin: 5px 0;
        font-size: 0.87rem; color: {BIAT_TEXT};
    }}

    /* ── Info box ── */
    .info-biat {{
        background: {BIAT_BLUE_LIGHT};
        border: 1px solid rgba(0,43,92,0.2);
        border-left: 4px solid {BIAT_BLUE};
        border-radius: 0 8px 8px 0;
        padding: 10px 14px; font-size: 0.84rem;
        color: {BIAT_BLUE}; margin: 8px 0;
    }}

    /* ── Badge forme juridique ── */
    .badge-part {{
        background: {BIAT_BLUE_LIGHT}; color: {BIAT_BLUE};
        padding: 5px 16px; border-radius: 20px;
        font-weight: 700; font-size: 0.85rem;
        border: 1px solid {BIAT_BLUE};
    }}
    .badge-pro {{
        background: #EAFAF1; color: #1B6B35;
        padding: 5px 16px; border-radius: 20px;
        font-weight: 700; font-size: 0.85rem;
        border: 1px solid #1B6B35;
    }}
    .badge-tre {{
        background: #FDEDEC; color: #C0392B;
        padding: 5px 16px; border-radius: 20px;
        font-weight: 700; font-size: 0.85rem;
        border: 1px solid #C0392B;
    }}
    .badge-enr {{
        background: #E8F8F5; color: #0F766E;
        padding: 5px 16px; border-radius: 20px;
        font-weight: 700; font-size: 0.85rem;
        border: 1px solid #0F766E;
    }}

    /* ── Description segment ── */
    .desc-card {{
        border-radius: 12px; padding: 18px 22px;
        margin: 8px 0; border-left: 6px solid;
    }}
    .desc-titre {{ font-size: 1.1rem; font-weight: 700; margin-bottom: 7px; }}
    .desc-texte {{ font-size: 0.9rem; line-height: 1.7; }}
    .desc-tag {{
        display: inline-block; padding: 3px 10px; border-radius: 12px;
        font-size: 0.76rem; font-weight: 500; margin: 2px;
    }}

    /* ── Chatbot ── */
    .chat-box {{
        background: {BIAT_GRAY}; border-radius: 12px;
        padding: 14px; margin-bottom: 10px;
        border: 1px solid #e2e8f0; max-height: 420px; overflow-y: auto;
    }}
    .msg-user {{
        background: {BIAT_BLUE}; color: white;
        border-radius: 12px 12px 2px 12px;
        padding: 10px 14px; margin: 6px 0 6px 50px;
        font-size: 0.87rem;
    }}
    .msg-bot {{
        background: white; color: {BIAT_TEXT};
        border-radius: 12px 12px 12px 2px;
        padding: 10px 14px; margin: 6px 50px 6px 0;
        font-size: 0.87rem; border: 1px solid #e2e8f0;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }}
    .msg-nom-bot {{ font-size: 0.72rem; color: {BIAT_ORANGE}; font-weight: 700; margin-bottom: 3px; }}
    .msg-nom-usr {{ font-size: 0.72rem; color: rgba(255,255,255,0.7); margin-bottom: 3px; text-align: right; }}

    /* ── Alerte dormant ── */
    .dormant-alert {{
        background: #FDEDEC; border: 1px solid #E74C3C;
        border-left: 4px solid #E74C3C; border-radius: 0 8px 8px 0;
        padding: 10px 14px; font-size: 0.85rem; color: #922B21;
    }}
    .actif-ok {{
        background: #EAFAF1; border: 1px solid #27AE60;
        border-left: 4px solid #27AE60; border-radius: 0 8px 8px 0;
        padding: 10px 14px; font-size: 0.85rem; color: #1B5E20;
    }}

    /* ── Pied de page BIAT ── */
    .biat-footer {{
        background: {BIAT_BLUE}; color: rgba(255,255,255,0.7);
        text-align: center; padding: 14px;
        border-radius: 10px; margin-top: 30px;
        font-size: 0.78rem;
        border-top: 3px solid {BIAT_ORANGE};
    }}

    /* ── Warn modif paramètre ── */
    .warn-param {{
        background: {BIAT_ORANGE_L}; border: 1px solid {BIAT_ORANGE};
        border-radius: 8px; padding: 8px 12px;
        font-size: 0.82rem; color: #92400e; margin: 5px 0;
    }}

    /* ── Section titre ── */
    .section-titre {{
        color: {BIAT_BLUE}; font-size: 1rem; font-weight: 700;
        border-bottom: 2px solid {BIAT_ORANGE};
        padding-bottom: 6px; margin-bottom: 14px;
    }}

    #MainMenu {{visibility:hidden;}} footer {{visibility:hidden;}}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# CONNEXION BDD
# ─────────────────────────────────────────────────────────────────────
@st.cache_resource
def init_db():
    try:
        from db_biat import BiatDB
        db = BiatDB()
        if db.connecter(): return db
    except Exception:
        pass
    return None

DB = init_db()

# ─────────────────────────────────────────────────────────────────────
# PROFESSIONS
# ─────────────────────────────────────────────────────────────────────
PROFESSIONS_HG_STATIC = [
    "Médecin généraliste","Médecin spécialiste","Médecin dentiste",
    "Médecin vétérinaire","Pharmacien","Biologiste et assimilé",
    "Opticien-lunetier","Avocat","Expert-comptable","Ingénieur","Architecte et urbaniste"
]
PROFESSIONS_LIB_STATIC = [
    "Médecin généraliste","Médecin spécialiste","Médecin dentiste",
    "Médecin vétérinaire","Pharmacien","Biologiste et assimilé","Expert-comptable"
]
PROFESSIONS_SAL_STATIC = [
    "Médecin généraliste","Médecin spécialiste","Médecin dentiste",
    "Pharmacien","Biologiste et assimilé","Magistrat","Enseignant universitaire",
    "Expert-comptable","Architecte et urbaniste","Ingénieur",
    "Chef de mission diplomatique","Haut fonctionnaire","Pilote et officier de pont"
]
AUTRES_PROFS = [
    "Salarié secteur privé","Fonctionnaire","Étudiant",
    "Commerçant","Artisan","Retraité","Sans profession","Autre"
]

def get_profs_hg():
    if DB:
        try: return DB.get_professions_potentiel()
        except: pass
    return PROFESSIONS_HG_STATIC

def get_profs_lib():
    if DB:
        try: return DB.get_professions_liberales()
        except: pass
    return PROFESSIONS_LIB_STATIC

def get_toutes_profs():
    if DB:
        try: return DB.get_professions_libelle()
        except: pass
    return sorted(set(PROFESSIONS_HG_STATIC+PROFESSIONS_SAL_STATIC+AUTRES_PROFS))

# ─────────────────────────────────────────────────────────────────────
## ─────────────────────────────────────────────────────────────────────
# PARAMÈTRES PAR DÉFAUT (Basés sur la Note 2023-06)
# ─────────────────────────────────────────────────────────────────────
DEFAUTS = {
    # --- MARCHÉ DES PARTICULIERS (PART) ---
    "vrd_fortunes": 500.0,      # VRD >= 500 mDT (Segment Fortunes)
    "vrd_pat_min": 300.0,       # VRD entre 300 et 500 mDT (Patrimoniaux)
    "vrd_pat_max": 500.0,
    "age_affluent": 30,         # Age minimum pour le segment Affluent
    "mmm_affluent": 4.0,        # MMM >= 4 mDT (Affluent)
    "vrd_aff_min": 100.0,       # VRD entre 100 et 300 mDT (Affluent)
    "vrd_aff_max": 300.0,
    "vrd_ep_hg": 100.0,         # Épargne >= 100 mDT (Haut de Gamme)

    # --- MARCHÉ DES PROFESSIONNELS (PRO) ---
    "vrd_pro_hg": 300.0,        # VRD >= 300 mDT (PRO Haut de Gamme)
    "vrd_lib_min": 100.0,       # VRD >= 100 mDT pour Professions Libérales (HG)
    "vrd_lib_max": 300.0,
    "mmm_pro_cm_min": 1.0,      # MMM entre 1 et 5 mDT (PRO Encadrés / TPME)
    "mmm_pro_cm_max": 5.0,
    "vrd_pro_pat_min": 300.0,   # VRD >= 300 mDT (PRO Patrimoniaux)

    # --- SEGMENT GRAND PUBLIC & JEUNES ---
    "age_cm": 30,               # Age pivot pour Classe Moyenne
    "mmm_sal_min": 1.0,         # MMM entre 1 et 4 mDT (Salariés CM)
    "mmm_sal_max": 4.0,
    "vrd_sal_min": 5.0,         # VRD entre 5 et 100 mDT (Salariés CM)
    "vrd_sal_max": 100.0,
    "vrd_ep_cm_min": 15.0,      # Épargne entre 15 et 100 mDT (Épargnants CM)
    "vrd_ep_cm_max": 100.0,
    "age_enfants": 18,          # Moins de 18 ans (Les Enfants)
    "age_jeunes": 30,           # Entre 18 et 30 ans (Les Jeunes)

    # --- TUNISIENS RÉSIDENTS À L'ÉTRANGER (TRE) ---
    "mmm_tre_p": 25.0,          # MMM >= 25 mDT (TRE Premium)
    "vrd_tre_p": 50.0,          # VRD >= 50 mDT (TRE Premium)
    "mmm_tre_m_min": 1.0,       # MMM entre 1 et 25 mDT (TRE Affluent)
    "mmm_tre_m_max": 25.0,
    "vrd_tre_m_min": 10.0,      # VRD entre 10 et 50 mDT (TRE Affluent)
    "vrd_tre_m_max": 50.0,

    # --- ENTREPRISES (ENR / PME) ---
    "mmm_enr_p": 10.0,          # MMM >= 10 mDT (ENR Premium)
    "vrd_enr_p": 60.0,          # VRD >= 60 mDT (ENR Premium)
    "mmm_enr_m_min": 5.0,       # MMM entre 5 et 10 mDT (Petites ENR)
    "mmm_enr_m_max": 10.0,
    "vrd_enr_m_min": 30.0,      # VRD entre 30 et 60 mDT (Petites ENR)
    "vrd_enr_m_max": 60.0,
}
# ─────────────────────────────────────────────────────────────────────
# MOTEUR DE SEGMENTATION
# ─────────────────────────────────────────────────────────────────────
def segmenter_client(client):
    marche = client.get("marche_input","")
    forme  = client.get("forme_juridique","Particulier")
    
    # Sécurité pour supprimer les PME (Asset Kings, etc.)
    # Si le marché est Entreprise, on ne traite pas ou on redirige
    if marche == "ENTREPRISE":
        return _res("HORS PÉRIMÈTRE", "Non classifié", "Marché PME exclu", ["Ce simulateur ne traite pas les PME (Asset Kings, PME Int, etc.)"])

    if marche == "TRE":   return _tre(client)
    elif marche == "ENR": return _enr(client)
    elif forme == "Professionnel": return _pro(client)
    else:                          return _part(client)

def _res(marche, seg, sous, expl):
    return {"marche":marche,"segment":seg,"sous_segment":sous,
            "couleur":COLORS.get(seg,"#6B7280"),
            "couleur_light":COLORS_LIGHT.get(seg,"#F5F5F5"),
            "explication":expl}


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _part(c):
    age=_safe_int(c.get("age",1),1); mmm=_safe_float(c.get("mmm",0.0),0.0); vrd=_safe_float(c.get("vrd",0.0),0.0)
    prof=c.get("profession",""); nb=_safe_int(c.get("nb_operations_12m",1),1); expl=[]
    HG=get_profs_hg(); LIB=get_profs_lib()

    if nb==0:
        expl.append("nb_operations_12m = 0 → Compte dormant automatiquement détecté")
        return _res("PART","Grand Public","Clients dormants",expl)
    P = st.session_state["params"]
    if vrd>=P["vrd_fortunes"]:
        expl.append(f"Particulier · VRD {vrd} mD ≥ {P['vrd_fortunes']} mD → Fortunés")
        return _res("PART","Haut de Gamme","Fortunés",expl)
    if P["vrd_pat_min"]<=vrd<P["vrd_pat_max"]:
        expl.append(f"Particulier · VRD {vrd} mD ∈ [{P['vrd_pat_min']},{P['vrd_pat_max']}[ mD → Patrimoniaux")
        return _res("PART","Haut de Gamme","Patrimoniaux",expl)
    if prof in LIB and P["vrd_lib_min"]<=vrd<P["vrd_lib_max"]:
        expl.append(f"Particulier · Profession libérale ({prof}) · VRD {vrd} mD → Prof. Libérales HG")
        return _res("PART","Haut de Gamme","Professions Libérales HG",expl)
    if age>=P["age_affluent"] and (mmm>=P["mmm_affluent"] or P["vrd_aff_min"]<=vrd<P["vrd_aff_max"]):
        expl.append(f"Particulier · âge {age} ≥ {P['age_affluent']} ans · MMM {mmm} mD / VRD {vrd} mD → Affluent")
        return _res("PART","Haut de Gamme","Affluent",expl)
    if mmm==0 and P["vrd_ep_hg"]<=vrd<P["vrd_aff_max"]:
        expl.append(f"Particulier · Épargnant exclusif · VRD {vrd} mD → Épargnants HG")
        return _res("PART","Haut de Gamme","Épargnants et déposants exclusifs HG",expl)

    if age>=P["age_cm"] and (P["mmm_sal_min"]<=mmm<P["mmm_sal_max"] or P["vrd_sal_min"]<=vrd<P["vrd_sal_max"]):
        expl.append(f"Particulier · âge {age} ≥ {P['age_cm']} ans · MMM {mmm} / VRD {vrd} → Salariés CM")
        return _res("PART","Classe Moyenne","Les Salariés",expl)
    if mmm==0 and P["vrd_ep_cm_min"]<=vrd<P["vrd_ep_cm_max"]:
        expl.append(f"Particulier · Épargnant CM · VRD {vrd} mD")
        return _res("PART","Classe Moyenne","Épargnants CM",expl)

    if age<=P["age_enfants"]:
        expl.append(f"Particulier · âge {age} ≤ {P['age_enfants']} ans → Enfants & Élèves")
        return _res("PART","Les Jeunes","Enfants et Élèves",expl)
    if P["age_enfants"]<age<=P["age_jeunes"] and prof in HG:
        expl.append(f"Particulier · âge {age} ≤ {P['age_jeunes']} · Profession à potentiel → JDA Potentiel")
        return _res("PART","Les Jeunes","JDA Potentiel",expl)
    if P["age_enfants"]<age<=P["age_jeunes"] and prof=="Étudiant":
        expl.append(f"Particulier · Étudiant · âge {age} → Étudiants")
        return _res("PART","Les Jeunes","Étudiants",expl)
    if P["age_enfants"]<age<=P["age_jeunes"]:
        expl.append(f"Particulier · âge {age} ≤ {P['age_jeunes']} · Autres professions → Autres JDA")
        return _res("PART","Les Jeunes","Autres JDA",expl)

    expl.append(f"Particulier · MMM {mmm} mD · VRD {vrd} mD → Grand Public")
    return _res("PART","Grand Public","Particuliers",expl)

def _pro(c):
    mmm = _safe_float(c.get("mmm", 0.0), 0.0)
    vrd = _safe_float(c.get("vrd", 0.0), 0.0)
    prof = c.get("profession", "")
    nb = _safe_int(c.get("nb_operations_12m", 1), 1)
    expl = []
    HG = get_profs_hg()
    LIB = get_profs_lib()

    # 1. Gestion des Dormants
    if nb == 0:
        expl.append("nb_operations_12m = 0 → Professionnel dormant automatiquement détecté")
        return _res("PRO", "Grand Public", "Clients dormants PRO", expl)

    # 2. PRO Haut de Gamme (HDG)
    # Règle Note Page 5 : MMM >= 5mD OU VRD >= 300mD
    if vrd >= 300 or mmm >= 5:
        expl.append(f"Professionnel · VRD {vrd}mD ≥ 300 OU MMM {mmm}mD ≥ 5 → Patrimoniaux PRO")
        return _res("PRO", "Haut de Gamme", "Patrimoniaux PRO", expl)
    
    # Cas particulier Prof. Libérales en PRO (Note Page 5)
    if prof in LIB and vrd >= 100:
        expl.append(f"Professionnel · Libéral ({prof}) · VRD {vrd}mD ≥ 100 → Professions Libérales HG")
        return _res("PRO", "Haut de Gamme", "Professions Libérales HG", expl)

    # 3. TPME / PRO Encadrés (Ce que l'encadrante veut garder)
    # Règle Note Page 5 : MMM [1, 5[ OU VRD [10, 300[
    if (1 <= mmm < 5) or (10 <= vrd < 300):
        expl.append(f"Professionnel · MMM {mmm}mD ∈ [1,5[ OU VRD {vrd}mD ∈ [10,300[ → PRO Encadrés (TPME)")
        return _res("PRO", "Classe Moyenne", "PRO Encadrés (TPME)", expl)

    # 4. PRO Standard (Grand Public)
    expl.append(f"Professionnel · MMM {mmm}mD < 1 → PRO Standard (Grand Public)")
    return _res("PRO", "Grand Public", "Commerçants & Artisans GP", expl)

def _tre(c):
    mmm=_safe_float(c.get("mmm",0.0), 0.0); vrd=_safe_float(c.get("vrd",0.0), 0.0)
    prof=c.get("profession",""); nb=_safe_int(c.get("nb_operations_12m",1), 1); expl=[]
    if nb==0:
        expl.append("TRE · nb_operations_12m = 0 → TRE Inactif")
        return _res("TRE","TRE","TRE Inactif",expl)
    P = st.session_state["params"]
    if prof in PROFESSIONS_SAL_STATIC or mmm>=P["mmm_tre_p"] or vrd>=P["vrd_tre_p"]:
        expl.append(f"TRE · MMM {mmm} mD OU VRD {vrd} mD → TRE Premium")
        return _res("TRE","TRE","Premium",expl)
    if P["mmm_tre_m_min"]<=mmm<P["mmm_tre_m_max"] or P["vrd_tre_m_min"]<=vrd<P["vrd_tre_m_max"]:
        expl.append(f"TRE · Potentiel moyen")
        return _res("TRE","TRE","Potentiel moyen",expl)
    if vrd>0 or mmm>0:
        expl.append("TRE · Faible potentiel")
        return _res("TRE","TRE","Faible potentiel",expl)
    expl.append("TRE · Aucun avoir → TRE Inactif")
    return _res("TRE","TRE","TRE Inactif",expl)

def _enr(c):
    mmm=_safe_float(c.get("mmm",0.0), 0.0); vrd=_safe_float(c.get("vrd",0.0), 0.0)
    nb=_safe_int(c.get("nb_operations_12m",1), 1); expl=[]
    if nb==0:
        expl.append("ENR · nb_operations_12m = 0 → ENR Inactif")
        return _res("ENR","ENR","ENR Inactif",expl)
    P = st.session_state["params"]
    if mmm>=P["mmm_enr_p"] or vrd>=P["vrd_enr_p"]:
        expl.append(f"ENR Premium · MMM {mmm} mD OU VRD {vrd} mD")
        return _res("ENR","ENR","Premium",expl)
    if P["mmm_enr_m_min"]<=mmm<P["mmm_enr_m_max"] or P["vrd_enr_m_min"]<=vrd<P["vrd_enr_m_max"]:
        expl.append("ENR · Potentiel moyen")
        return _res("ENR","ENR","Potentiel moyen",expl)
    if vrd>0 or mmm>0:
        expl.append("ENR · Faible potentiel")
        return _res("ENR","ENR","Faible potentiel",expl)
    expl.append("ENR Inactif")
    return _res("ENR","ENR","ENR Inactif",expl)

# ─────────────────────────────────────────────────────────────────────
# DESCRIPTIONS
# ─────────────────────────────────────────────────────────────────────
DESCS = {
    "Haut de Gamme":{"bg":"#FEF9E7","bord":"#B8860B","i":"🏆",
        "d":"Le segment Haut de Gamme regroupe les clients les plus aisés de la BIAT. Ils bénéficient d'une prise en charge personnalisée et de services bancaires premium adaptés à leur profil patrimonial.",
        "s":{"Fortunés":{"d":"Particuliers avec avoirs très élevés (VRD ≥ 500 mD = 500 000 DT). Segment le plus exclusif de la BIAT.","p":["VRD ≥ 500 000 DT","Particulier"]},
             "Patrimoniaux":{"d":"Clients avec un patrimoine bancaire significatif (300–500 mD). Profil stable et patrimonial.","p":["VRD ∈ [300–500 mD["]},
             "Affluent":{"d":"Particuliers adultes avec de bons mouvements mensuels ou avoirs confortables. Clientèle aisée active.","p":["Âge ≥ 30 ans","MMM ≥ 4 mD OU VRD ∈ [100–300 mD["]},
             "Professions Libérales HG":{"d":"Médecins, pharmaciens, experts-comptables... avec avoirs confortables. Potentiel de croissance élevé.","p":["Profession libérale (Annexe 5)","VRD ∈ [100–300 mD["]},
             "Professionnels HG":{"d":"Professionnels à fort potentiel (Annexe 4) avec avoirs élevés. Cible stratégique.","p":["Profession à potentiel (Annexe 4)","VRD ≥ 300 mD"]},
             "Épargnants et déposants exclusifs HG":{"d":"Épargnants exclusifs avec patrimoine conséquent. Profil passif à fort potentiel.","p":["MMM = 0","VRD ∈ [100–300 mD["]},
             "Patrimoniaux PRO":{"d":"Professionnels avec un très grand patrimoine bancaire.","p":["Professionnel","VRD ≥ 300 mD"]},
             "Épargnants PRO HG":{"d":"Professionnels épargnants exclusifs avec patrimoine conséquent.","p":["Professionnel","MMM = 0","VRD ∈ [100–300 mD["]},
        }},
    "Classe Moyenne":{"bg":"#EAFAF1","bord":"#1B6B35","i":"🟢",
        "d":"La Classe Moyenne regroupe des clients avec des revenus et avoirs intermédiaires. Ce sont principalement des salariés, commerçants et artisans constituant le cœur de la clientèle de masse.",
        "s":{"Les Salariés":{"d":"Particuliers adultes salariés avec mouvements mensuels dans la tranche moyenne.","p":["Âge ≥ 30 ans","MMM ∈ [1–4 mD[ OU VRD ∈ [5–100 mD["]},
             "Épargnants CM":{"d":"Épargnants avec avoirs modérés et sans mouvements courants.","p":["MMM = 0","VRD ∈ [15–100 mD["]},
             "Commerçants & Artisans CM":{"d":"Professionnels avec activité transactionnelle modérée.","p":["Professionnel","MMM ∈ [1–5 mD["]},
             "Épargnants PRO CM":{"d":"Professionnels épargnants avec avoirs modérés.","p":["Professionnel","MMM = 0","VRD ∈ [15–100 mD["]},
        }},
    "Grand Public":{"bg":"#EAF2FF","bord":"#004080","i":"🔵",
        "d":"Le Grand Public regroupe la clientèle de masse avec des niveaux de revenus et d'avoirs modestes. L'objectif est de les accompagner dans leur bancarisation et évolution.",
        "s":{"Particuliers":{"d":"Clients particuliers avec faibles mouvements et avoirs.","p":["MMM < 1 mD","VRD < 5 mD"]},
             "Commerçants & Artisans GP":{"d":"Professionnels avec faible activité transactionnelle.","p":["Professionnel","MMM < 1 mD"]},
             "Clients dormants":{"d":"⚠️ Comptes sans aucun mouvement depuis plus d'un an (nb_operations_12m = 0). Détection automatique. Action de réactivation urgente recommandée.","p":["nb_operations_12m = 0","⚠️ Réactivation urgente"]},
             "Clients dormants PRO":{"d":"⚠️ Comptes professionnels sans mouvement depuis 1 an. Détection automatique.","p":["Professionnel","nb_operations_12m = 0","⚠️ Réactivation urgente"]},
        }},
    "Les Jeunes":{"bg":"#F5EEF8","bord":"#6B21A8","i":"🟣",
        "d":"Le segment Jeunes cible les clients de moins de 30 ans. Segment stratégique représentant les clients de demain. L'objectif est de les fidéliser tôt.",
        "s":{"Enfants et Élèves":{"d":"Clients de moins de 18 ans, comptes ouverts par les parents.","p":["Âge ≤ 18 ans"]},
             "Étudiants":{"d":"Jeunes de moins de 30 ans poursuivant des études.","p":["Âge ≤ 30 ans","Profession = Étudiant"]},
             "JDA Potentiel":{"d":"Jeunes Diplômés à fort potentiel (médecins, ingénieurs...). Les futurs clients HG de la BIAT.","p":["Âge ≤ 30 ans","Profession à potentiel (Annexe 4)"]},
             "Autres JDA":{"d":"Jeunes adultes de moins de 30 ans avec autres professions.","p":["Âge ≤ 30 ans","Autres professions"]},
        }},
    "TRE":{"bg":"#FDEDEC","bord":"#C0392B","i":"🌍",
        "d":"Le marché TRE regroupe les Tunisiens établis à l'étranger maintenant une relation bancaire avec la BIAT. Source importante de devises et de transferts.",
        "s":{"Premium":{"d":"TRE à fort potentiel ou profession à potentiel. Services premium dédiés.","p":["MMM ≥ 25 mD OU VRD ≥ 50 mD"]},
             "Potentiel moyen":{"d":"TRE avec activité bancaire modérée. Potentiel à développer.","p":["MMM ∈ [1–25 mD[ OU VRD ∈ [25–50 mD["]},
             "Faible potentiel":{"d":"TRE avec peu d'activité bancaire en Tunisie.","p":["MMM < 1 mD ET VRD < 25 mD"]},
             "TRE Inactif":{"d":"TRE sans mouvements depuis 1 an. Détection automatique via nb_operations_12m = 0.","p":["nb_operations_12m = 0","⚠️ Réactivation"]},
        }},
    "ENR":{"bg":"#E8F8F5","bord":"#0F766E","i":"🌐",
        "d":"Le marché ENR regroupe les étrangers non résidents. Séjour en Tunisie ≤ 3 mois consécutifs.",
        "s":{"Premium":{"d":"ENR à fort potentiel avec mouvements ou avoirs élevés.","p":["MMM ≥ 10 mD OU VRD ≥ 60 mD"]},
             "Potentiel moyen":{"d":"ENR avec activité bancaire intermédiaire.","p":["MMM ∈ [5–10 mD[ OU VRD ∈ [30–60 mD["]},
             "Faible potentiel":{"d":"ENR avec peu d'activité.","p":["MMM < 5 mD ET VRD < 30 mD"]},
             "ENR Inactif":{"d":"ENR sans mouvements depuis 1 an. Détection automatique.","p":["nb_operations_12m = 0"]},
        }},
}

def afficher_description(res):
    seg=res["segment"]; sous=res["sous_segment"]
    d=DESCS.get(seg,{})
    if not d: return
    bg=d["bg"]; bord=d["bord"]
    st.markdown("---")
    st.markdown(f'<div class="section-titre">📖 Description du segment attribué</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="desc-card" style="background:{bg};border-left-color:{bord};">
        <div class="desc-titre" style="color:{bord};">{d["i"]} {seg}</div>
        <div class="desc-texte">{d["d"]}</div>
    </div>""", unsafe_allow_html=True)
    sd=d.get("s",{}).get(sous,{})
    if sd:
        tags="".join([f'<span class="desc-tag" style="background:{bg};color:{bord};border:1px solid {bord};">{p}</span>' for p in sd.get("p",[])])
        st.markdown(f"""
        <div style="background:white;border:1px solid {bord};border-radius:10px;padding:14px;margin-top:8px;">
            <div style="font-weight:700;color:{bord};margin-bottom:6px;">📌 {sous}</div>
            <div style="font-size:.9rem;color:{BIAT_TEXT};line-height:1.7;margin-bottom:10px;">{sd.get("d","")}</div>
            <div>{tags}</div>
        </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# RAPPORT PDF
# ─────────────────────────────────────────────────────────────────────
def generer_pdf(res, client):
    now   = datetime.now().strftime("%d/%m/%Y à %H:%M")
    color = res["couleur"]; light = res["couleur_light"]
    nb    = client.get("nb_operations_12m","—")
    actif = "Actif ✅" if (nb != "—" and int(nb) > 0) else "Dormant ⚠️"

    logo_svg = LOGO_BIAT_SVG.replace('"','\'')

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Rapport BIAT Segmentation</title>
<style>
  body{{font-family:Arial,sans-serif;margin:0;color:#1A2B4A;font-size:13px;}}
  .header{{background:{BIAT_BLUE};padding:20px 30px;display:flex;
           align-items:center;justify-content:space-between;}}
  .header-right{{color:white;text-align:right;}}
  .header-right h1{{margin:0;font-size:1.3rem;font-weight:700;}}
  .header-right p{{margin:4px 0 0;opacity:.75;font-size:.8rem;}}
  .orange-bar{{background:{BIAT_ORANGE};height:5px;}}
  .content{{padding:24px 30px;}}
  .result{{border:2px solid {color};border-radius:10px;padding:18px;
           text-align:center;margin:16px 0;background:{light};
           border-bottom:4px solid {BIAT_ORANGE};}}
  .r-m{{color:{color};font-size:.88rem;margin-bottom:3px;}}
  .r-s{{font-size:1.8rem;font-weight:800;color:{color};}}
  .r-ss{{font-size:1rem;color:{color};margin-top:3px;}}
  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:12px 0;}}
  .item{{background:#F4F6F9;padding:10px 12px;border-radius:6px;
         border-left:3px solid {BIAT_ORANGE};}}
  .il{{font-size:.7rem;color:#6B7280;}}
  .iv{{font-weight:700;font-size:.9rem;}}
  .regle{{background:{BIAT_ORANGE_L};border-left:4px solid {BIAT_ORANGE};
          padding:7px 12px;margin:5px 0;border-radius:0 6px 6px 0;font-size:.85rem;}}
  h2{{font-size:.95rem;color:{BIAT_BLUE};border-bottom:2px solid {BIAT_ORANGE};
      padding-bottom:5px;margin:18px 0 10px;}}
  .footer{{background:{BIAT_BLUE};color:rgba(255,255,255,.7);text-align:center;
           padding:14px;font-size:.75rem;border-top:3px solid {BIAT_ORANGE};
           margin-top:30px;}}
  @media print{{body{{margin:0;}}}}
</style>
</head>
<body>
<div class="header">
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 70" width="160" height="50">
    <rect width="220" height="70" rx="4" fill="rgba(255,255,255,0.1)"/>
    <polygon points="18,10 34,10 22,50 6,50" fill="white" opacity="0.95"/>
    <text x="44" y="42" font-family="Arial Black,Arial" font-weight="900"
          font-size="28" fill="white" letter-spacing="2">BIAT</text>
    <rect y="56" width="220" height="8" fill="{BIAT_ORANGE}"/>
  </svg>
  <div class="header-right">
    <h1>Rapport de Segmentation Clientèle</h1>
    <p>Pôle Banque de Détail · Note PBD N°2023-06 · {now}</p>
  </div>
</div>
<div class="orange-bar"></div>
<div class="content">
<div class="result">
  <div class="r-m">Marché : {res['marche']}</div>
  <div class="r-s">{res['segment']}</div>
  <div class="r-ss">{res['sous_segment']}</div>
</div>
<h2>Informations du client</h2>
<div class="grid">
  <div class="item"><div class="il">Marché</div><div class="iv">{res['marche']}</div></div>
  <div class="item"><div class="il">Forme juridique</div><div class="iv">{client.get('forme_juridique','—')}</div></div>
  <div class="item"><div class="il">Âge</div><div class="iv">{client.get('age','—')} ans</div></div>
  <div class="item"><div class="il">Profession</div><div class="iv">{client.get('profession','—')}</div></div>
  <div class="item"><div class="il">MMM (mD)</div><div class="iv">{client.get('mmm','—')} mD</div></div>
  <div class="item"><div class="il">VRD (mD)</div><div class="iv">{client.get('vrd','—')} mD</div></div>
  <div class="item"><div class="il">Résidence</div><div class="iv">{client.get('residence','—')}</div></div>
  <div class="item"><div class="il">Nb opérations (12 mois)</div><div class="iv">{nb}</div></div>
</div>
<div class="item" style="margin-top:8px;">
  <div class="il">Statut du compte (calculé automatiquement)</div>
  <div class="iv">{actif}</div>
</div>
<h2>Règles de segmentation appliquées</h2>
{"".join([f'<div class="regle">✅ {r}</div>' for r in res.get("explication",[])])}
</div>
<div class="footer">
  BIAT — Banque Internationale Arabe de Tunisie &nbsp;|&nbsp;
  Pôle Banque de Détail · Direction Marketing et Développement Digital &nbsp;|&nbsp;
  Simulateur de Segmentation v5.0
</div>
<script>window.onload=function(){{window.print();}}</script>
</body></html>"""

    b64 = base64.b64encode(html.encode("utf-8")).decode()
    st.markdown(f"""
    <div style="text-align:center;margin:16px 0;">
        <a href="data:text/html;base64,{b64}" download="rapport_segmentation_biat.html"
           style="background:{BIAT_BLUE};color:white;padding:12px 28px;border-radius:8px;
                  text-decoration:none;font-weight:700;font-size:.92rem;display:inline-block;
                  border-bottom:3px solid {BIAT_ORANGE};">
            🖨️ Télécharger et imprimer le rapport
        </a>
        &nbsp;&nbsp;
        <span style="font-size:.78rem;color:{BIAT_GRAY_DARK};">
            Ouvrez le fichier → l'impression se lance automatiquement
        </span>
    </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# CHATBOT
# ─────────────────────────────────────────────────────────────────────
KB = {
    "mmm":f"Le **MMM** (Mouvements Mensuels Moyens) = moyenne mensuelle des mouvements créditeurs calculée dans T24. Unité : **mD** (milliers de Dinars Tunisiens). Ex : 3 mD = 3 000 DT/mois.",
    "vrd":"Le **VRD** (Valeur en Dépôts) = Total avoirs stables = Dépôts à vue + Épargne + Dépôts à terme. Unité : mD.",
    "md":"**mD** = milliers de Dinars Tunisiens. 1 mD = 1 000 DT · 4 mD = 4 000 DT · 500 mD = 500 000 DT.",
    "part":"Le marché **Particuliers (PART)** = personnes physiques résidentes tunisiennes sans activité professionnelle déclarée. Segments : Haut de Gamme · Classe Moyenne · Grand Public · Les Jeunes.",
    "pro":"Le marché **Professionnels (PRO)** = personnes physiques résidentes exerçant une activité professionnelle. Séparé du marché PART depuis la Note 2023.",
    "tre":"Le marché **TRE** = Tunisiens Résidents à l'Étranger. 4 sous-segments : Premium (MMM ≥ 25 mD ou VRD ≥ 50 mD), Potentiel moyen, Faible potentiel, Inactif.",
    "enr":"Le marché **ENR** = Étrangers Non Résidents. Séjour ≤ 3 mois en Tunisie. Premium : MMM ≥ 10 mD ou VRD ≥ 60 mD.",
    "haut de gamme":"Le **Haut de Gamme** : Fortunés (VRD ≥ 500 mD), Patrimoniaux (300–500 mD), Affluent (âge ≥ 30 + MMM ≥ 4 mD), Professions Libérales, Épargnants HG, Professionnels HG.",
    "fortuné":"Les **Fortunés** = Particuliers avec VRD ≥ 500 mD (500 000 DT). Segment le plus exclusif de la BIAT.",
    "affluent":"L'**Affluent** = Particulier · âge ≥ 30 ans · MMM ≥ 4 mD OU VRD ∈ [100,300[ mD. Clientèle aisée et active.",
    "classe moyenne":"La **Classe Moyenne** : Salariés (âge ≥ 30, MMM 1–4 mD), Épargnants CM, Commerçants & Artisans PRO (MMM 1–5 mD).",
    "grand public":"Le **Grand Public** : clients MMM < 1 mD · VRD < 5 mD + Clients dormants.",
    "dormant":"Un **client dormant** = compte avec **nb_operations_12m = 0** (aucun mouvement depuis 1 an). Le simulateur le détecte **automatiquement** sans que l'utilisateur ait à cocher une case.",
    "nb_operations":"**nb_operations_12m** = nombre d'opérations sur les 12 derniers mois. Si = 0 → client automatiquement classé **Dormant**. Calcul automatique.",
    "jda":"**JDA Potentiel** = Jeune Diplômé à fort potentiel. Moins de 30 ans + profession à potentiel (médecin, ingénieur, avocat...). Futurs clients Haut de Gamme.",
    "jeunes":"Le segment **Jeunes** : Enfants & Élèves (≤ 18 ans), Étudiants, JDA Potentiel, Autres JDA (≤ 30 ans).",
    "paramètre":"Les **paramètres** = seuils officiels modifiables dans le panneau gauche bleu. Changer ex: âge Affluent de 30 à 25 ans. Bouton orange 'Restaurer' remet les valeurs officielles BIAT.",
    "imprimer":"Pour **imprimer** : lancez une simulation → cliquez sur '🖨️ Télécharger et imprimer le rapport' → le fichier HTML s'ouvre et l'impression démarre automatiquement.",
    "biat":"La **BIAT** (Banque Internationale Arabe de Tunisie) est la 1ère banque privée tunisienne. Ce simulateur couvre le Pôle Banque de Détail avec 4 marchés : PART · PRO · TRE · ENR.",
    "logo":"Le logo BIAT présente un fond bleu marine **#002B5C** avec le texte blanc **BIAT** et une barre orange **#F5A623** en bas. Ce sont les couleurs officielles utilisées dans ce simulateur.",
    "couleur":"Les couleurs officielles BIAT sont : **Bleu marine #002B5C** (couleur principale), **Orange #F5A623** (couleur accent). Ces couleurs sont utilisées dans toute l'interface de ce simulateur.",
}

def repondre(q):
    ql = q.lower()
    if any(w in ql for w in ["bonjour","salut","hello","bonsoir"]):
        return f"Bonjour ! 👋 Je suis **BIATBot**, l'assistant officiel du simulateur BIAT. Je connais les marchés PART, PRO, TRE, ENR, les variables MMM/VRD et toutes les règles de segmentation. Comment puis-je vous aider ?"
    if any(w in ql for w in ["merci","thank"]):
        return "Avec plaisir ! 😊 N'hésitez pas pour toute autre question."
    if any(w in ql for w in ["aide","help"]):
        return "Je peux vous aider sur : **MMM · VRD · mD · PART · PRO · TRE · ENR · Haut de Gamme · Affluent · Dormant · JDA · Paramètres · Impression · Logo · Couleurs**"
    for mot,rep in KB.items():
        if mot in ql: return rep
    if any(w in ql for w in ["profession","annexe 4"]):
        return "**Professions à potentiel (Annexe 4)** : Médecin généraliste, Médecin spécialiste, Médecin dentiste, Vétérinaire, Pharmacien, Biologiste, Opticien-lunetier, Avocat, Expert-comptable, Ingénieur, Architecte et urbaniste."
    if any(w in ql for w in ["sépar","différence part pro"]):
        return "**PART vs PRO séparés** :\n- **PART** = Particuliers (personnes sans activité pro)\n- **PRO** = Professionnels (médecins, commerçants, artisans...)\n\nChaque marché a ses propres segments et seuils distincts. Vous pouvez les sélectionner séparément dans le simulateur."
    return "Je n'ai pas trouvé de réponse précise. 🤔 Essayez : **MMM, VRD, PART, PRO, TRE, ENR, dormant, JDA, Affluent, Haut de Gamme, paramètre, imprimer, couleur, logo**."

# ─────────────────────────────────────────────────────────────────────
# DONNÉES DÉMO
# ─────────────────────────────────────────────────────────────────────
def generer_demo(n=300):
    random.seed(42); np.random.seed(42)
    profs = get_toutes_profs()
    rows  = []
    for i in range(n):
        forme = random.choice(["Particulier","Particulier","Particulier","Professionnel"])
        marche = random.choices(["PART & PRO","TRE","ENR"], weights=[70,20,10])[0]
        nb_ops = random.choices([0]+list(range(1,120)), weights=[15]+[85/119]*119)[0]
        rows.append({
            "id_client": f"CLI{i+1:04d}",
            "marche_input": marche,
            "forme_juridique": forme,
            "age": int(np.clip(np.random.normal(38,15),1,90)),
            "mmm": round(abs(np.random.exponential(4)),2),
            "vrd": round(abs(np.random.exponential(60)),2),
            "profession": random.choice(profs),
            "nb_operations_12m": nb_ops,
        })
    return pd.DataFrame(rows)

# ─────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────
# CONFIGURATION DE LA BARRE LATÉRALE (SIDEBAR)
# ─────────────────────────────────────────────────────────────────────
def render_sidebar():
    """
    Gère l'interface de configuration des paramètres de segmentation.
    Permet une flexibilité totale si les seuils de la Note 2023-06 évoluent.
    """
    # INITIALISATION : On vérifie si les paramètres existent, sinon on charge les DEFAUTS
    if "params" not in st.session_state:
        st.session_state["params"] = DEFAUTS.copy()
    
    # On définit 'P' pour pouvoir l'utiliser dans toute la fonction
    P = st.session_state["params"]

    with st.sidebar:
        # Affichage du Logo BIAT pour renforcer l'identité visuelle
        st.markdown(f"""
        <div style="text-align:center;padding:16px 0 8px;">
            <img src="data:image/svg+xml;base64,{LOGO_B64}" width="160" alt="BIAT">
        </div>
        <div style="text-align:center;color:rgba(255,255,255,0.6);font-size:0.72rem;margin-bottom:16px;letter-spacing:0.3px;">
            PÔLE BANQUE DE DÉTAIL
        </div>
        """, unsafe_allow_html=True)

        # Indicateur visuel de conformité avec les seuils officiels
        nb_m = sum(1 for k in DEFAUTS if P.get(k) != DEFAUTS[k])
        if nb_m: 
            st.warning(f"⚠️ {nb_m} seuil(s) modifié(s)")
        else: 
            st.success("✅ Valeurs officielles BIAT")

        # Bouton de réinitialisation
        if st.button("🔄 Restaurer valeurs officielles", use_container_width=True):
            st.session_state["params"] = DEFAUTS.copy()
            st.rerun()

        st.markdown("---")

        # 1. SEGMENTATION MARCHÉ PART (Particuliers)
        with st.expander("👤 PART — Haut de Gamme", expanded=False):
            P["vrd_fortunes"] = st.number_input("VRD min Fortunés (mD)", 0.0, 99999.0, float(P["vrd_fortunes"]), 10.0)
            P["age_affluent"] = st.number_input("Âge min Affluent (ans)", 1, 99, int(P["age_affluent"]), 1)
            P["mmm_affluent"] = st.number_input("MMM min Affluent (mD)", 0.0, 9999.0, float(P["mmm_affluent"]), 0.5, help=f"Officiel : {DEFAUTS['mmm_affluent']} mD")
            
            # Ajout des inputs VRD pour Affluent et Patrimoniaux (كما في الكود الأصلي متاعك)
            c1,c2=st.columns(2)
            with c1: P["vrd_aff_min"]=st.number_input("VRD min Aff.",0.0,9999.0,float(P["vrd_aff_min"]),10.0,key="am")
            with c2: P["vrd_aff_max"]=st.number_input("VRD max Aff.",0.0,9999.0,float(P["vrd_aff_max"]),10.0,key="ax")
            c1,c2=st.columns(2)
            with c1: P["vrd_pat_min"]=st.number_input("VRD min Pat.",0.0,99999.0,float(P["vrd_pat_min"]),10.0,key="pm")
            with c2: P["vrd_pat_max"]=st.number_input("VRD max Pat.",0.0,99999.0,float(P["vrd_pat_max"]),10.0,key="px")

        # 2. SEGMENTATION MARCHÉ PRO (Professionnels)
        with st.expander("💼 PRO — Professionnels", expanded=False):
            P["vrd_pro_hg"] = st.number_input("VRD min Pro HG (mD)", 0.0, 9999.0, float(P["vrd_pro_hg"]), 10.0)
            c1, c2 = st.columns(2)
            with c1: P["mmm_pro_cm_min"] = st.number_input("MMM min Pro CM", 0.0, 9999.0, float(P["mmm_pro_cm_min"]), 0.5)
            with c2: P["mmm_pro_cm_max"] = st.number_input("MMM max Pro CM", 0.0, 9999.0, float(P["mmm_pro_cm_max"]), 0.5)

        st.markdown("---")
        
        # 3. CONNECTIVITÉ BASE DE DONNÉES
        if DB:
            st.markdown(f'<div style="color:{BIAT_ORANGE};font-weight:600;font-size:.82rem;">🗄️ MySQL connecté ✅</div>', unsafe_allow_html=True)
            stats = DB.get_stats_globales()
            st.metric("Simulations enregistrées", stats.get("total_simulations", 0))
        else:
            st.markdown('<div style="color:rgba(255,255,255,.5);font-size:.78rem;">🗄️ Mode hors ligne (sans MySQL)</div>', unsafe_allow_html=True)

        # MISE À JOUR : On réinjecte 'P' dans le session_state
        st.session_state["params"] = P
# ─────────────────────────────────────────────────────────────────────
# # ─────────────────────────────────────────────────────────────────────
# PAGE 1 — SIMULATION INDIVIDUELLE
# ─────────────────────────────────────────────────────────────────────
def page_individuelle():
    P = st.session_state["params"] 
    nb_ops = 0
    marche_input = "PART & PRO"
    forme_jur = "Particulier"
    age = 18
    mmm = 0.0
    vrd = 0.0
    profession = "Autre"
    residence = "Résident"
    nationalite = "Tunisienne"
    st.markdown(f'<div class="section-titre">🔍 Simulation individuelle</div>', unsafe_allow_html=True)
    st.caption("Renseignez les données du client pour obtenir son segment officiel BIAT.")

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown(f'<div class="section-titre">👤 Profil du client</div>', unsafe_allow_html=True)

        marche_choix = st.radio(
            "Sélectionner le marché",
            ["👤 Particulier (PART)", "💼 Professionnel (PRO)", "🌍 TRE", "🌐 ENR"],
            horizontal=True
        )

        # Mapping des entrées vers les variables du moteur
        if "Particulier" in marche_choix:
            forme_jur = "Particulier"
            marche_input = "PART & PRO"
            st.markdown(f'<span class="badge-part">👤 Marché Particuliers (PART)</span>', unsafe_allow_html=True)
        elif "Professionnel" in marche_choix:
            forme_jur = "Professionnel"
            marche_input = "PART & PRO"
            st.markdown(f'<span class="badge-pro">💼 Marché Professionnels (PRO)</span>', unsafe_allow_html=True)
        elif "TRE" in marche_choix:
            forme_jur = "Particulier"
            marche_input = "TRE"
            st.markdown(f'<span class="badge-tre">🌍 Tunisiens Résidents à l\'Étranger</span>', unsafe_allow_html=True)
        else:
            forme_jur = "Particulier"
            marche_input = "ENR"
            st.markdown(f'<span class="badge-enr">🌐 Étrangers Non Résidents</span>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        age = st.number_input("Âge du client (ans)", min_value=1, max_value=120, value=35, step=1)
        profs = get_toutes_profs()
        profession = st.selectbox("Profession", profs)
        
        c1, c2 = st.columns(2)
        with c1: residence = st.selectbox("Résidence", ["Résident","Non Résident"])
        with c2: nationalite = st.selectbox("Nationalité", ["Tunisienne","Étrائعة","Double"])

    with col2:
        st.markdown(f'<div class="section-titre">💰 Données financières</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="info-biat">
            <strong>MMM</strong> = Mouvements Mensuels Moyens (source T24)<br>
            <strong>VRD</strong> = Dépôts vue + Épargne + Dépôts terme<br>
            <strong>mD</strong> = milliers de Dinars · Exemple : 3 mD = 3 000 DT
        </div>""", unsafe_allow_html=True)

        mmm = st.number_input("MMM — Mouvements Mensuels Moyens (mD)",
                               0.0, 999999.0, 3.0, 0.1, format="%.3f")
        vrd = st.number_input("VRD — Total Avoirs Stables (mD)",
                               0.0, 999999.0, 50.0, 1.0, format="%.3f")
        nb_ops = st.number_input(
            "Nombre d'opérations (12 derniers mois)",
            min_value=0, max_value=9999, value=24, step=1,
            help="⚠️ Si = 0 → client automatiquement classé Dormant"
        )

      # --- Saisie des données client (Inputs) ---
    # (Tes colonnes c1, c2, c3 avec MMM, VRD, etc. sont juste au-dessus)

    st.markdown("---") # Ligne de séparation pour une interface propre

    # Centrer le bouton de lancement
    _, btn_col, _ = st.columns([1,2,1])
    with btn_col:
        lancer = st.button("🚀 Lancer la simulation", type="primary", use_container_width=True)

    if lancer:
        # 1. Préparation du dictionnaire client pour le moteur
        client = {
            "marche_input": marche_input,
            "forme_juridique": forme_jur,
            "age": int(age),
            "mmm": float(mmm),
            "vrd": float(vrd),
            "profession": profession,
            "residence": residence,
            "nationalite": nationalite,
            "nb_operations_12m": int(nb_ops),
        }
        
        # 2. Appel du moteur de segmentation
        res = segmenter_client(client)
        color = res["couleur"]
        light = res["couleur_light"]

        st.markdown("---")
        st.markdown(f'<div class="section-titre">🎯 Résultat de la simulation</div>', unsafe_allow_html=True)

        # 3. Affichage visuel du résultat (Box colorée)
        st.markdown(f"""
        <div class="resultat-box" style="background:{light}; border: 2px solid {color}; padding:20px; border-radius:10px; text-align:center;">
            <div class="r-marche" style="color:{color}; font-weight:bold;">Marché : {res['marche']}</div>
            <div class="r-segment" style="color:{color}; font-size:2rem; font-weight:800;">{res['segment']}</div>
            <div class="r-sous" style="color:{color}; font-size:1.2rem; opacity:0.8;">{res['sous_segment']}</div>
        </div>""", unsafe_allow_html=True)
        # 4. Affichage des KPIs (Cards)
        c1, c2, c3, c4 = st.columns(4)
        for col, (lbl, val) in zip([c1, c2, c3, c4], [
            ("Marché", res["marche"]),
            ("Segment", res["segment"]),
            ("Sous-segment", res["sous_segment"]),
            
        ]):
            col.markdown(f"""
                <div class="kpi-card" style="border:1px solid #ddd; padding:10px; border-radius:5px; text-align:center;">
                    <div class="kpi-val" style="color:{color}; font-weight:bold;">{val}</div>
                    <div class="kpi-lbl" style="font-size:0.8rem; color:gray;">{lbl}</div>
                </div>""", unsafe_allow_html=True)

        # 5. Justification et PDF
        st.markdown(f'<div class="section-titre" style="margin-top:16px;">📌 Règles appliquées</div>', unsafe_allow_html=True)
        for r in res["explication"]:
            st.markdown(f'<div class="regle-item" style="padding:5px 0;">✅ {r}</div>', unsafe_allow_html=True)

        afficher_description(res)
        
        st.markdown("---")
        generer_pdf(res, client)

        # 6. Sauvegarde Base de données
        if DB:
            P = st.session_state["params"]
            try:
                DB.sauvegarder_simulation(client, res, P)
                st.success("💾 Simulation sauvegardée en base MySQL")
            except Exception as e:
                st.warning(f"⚠️ BDD : {e}")

        # 7. Alerte si les paramètres ne sont pas ceux par défaut
        nb_m = sum(1 for k in DEFAUTS if P.get(k) != DEFAUTS[k])
        if nb_m:
            st.warning(f"⚠️ {nb_m} seuil(s) modifié(s) — résultat basé sur paramètres personnalisés.")
# ─────────────────────────────────────────────────────────────────────
# PAGE 2 — MASSE
# ─────────────────────────────────────────────────────────────────────
def page_masse():
    st.markdown(f'<div class="section-titre">📊 Simulation en masse</div>', unsafe_allow_html=True)
    st.caption("Colonnes CSV requises : marche_input · forme_juridique · age · mmm · vrd · profession · nb_operations_12m")

    c1,c2=st.columns([2,1])
    with c1: uploaded=st.file_uploader("📂 Importer un fichier CSV",type=["csv"])
    with c2:
        st.markdown("<br>",unsafe_allow_html=True)
        use_demo=st.button("🎲 Données de démonstration (300 clients)",use_container_width=True)

    df=None
    if uploaded:
        df=pd.read_csv(uploaded); st.success(f"✅ {len(df)} clients importés")
    elif use_demo:
        df=generer_demo(300); st.success("✅ 300 clients générés — PART · PRO · TRE · ENR")

    if df is not None:
        with st.spinner("⏳ Segmentation en cours..."):
            results=df.apply(lambda r: segmenter_client(r.to_dict()),axis=1)
            df["marche_res"] =results.apply(lambda x: x["marche"])
            df["segment"]    =results.apply(lambda x: x["segment"])
            df["sous_segment"]=results.apply(lambda x: x["sous_segment"])

        if "nb_operations_12m" in df.columns:
            df["est_actif"]=df["nb_operations_12m"]>0
            n_dorm=(df["nb_operations_12m"]==0).sum()
        else:
            n_dorm=0

        total=len(df)
        c1,c2,c3,c4,c5,c6=st.columns(6)
        for col,(lbl,val,clr) in zip([c1,c2,c3,c4,c5,c6],[
            ("Total",              total,                                    BIAT_BLUE),
            ("Haut de Gamme",     (df["segment"]=="Haut de Gamme").sum(),   COLORS["Haut de Gamme"]),
            ("Classe Moyenne",    (df["segment"]=="Classe Moyenne").sum(),  COLORS["Classe Moyenne"]),
            ("TRE",               (df["segment"]=="TRE").sum(),             COLORS["TRE"]),
            ("ENR",               (df["segment"]=="ENR").sum(),             COLORS["ENR"]),
            ("🔴 Dormants",       n_dorm,                                   "#C0392B"),
        ]):
            col.markdown(f'<div class="kpi-card"><div class="kpi-val" style="color:{clr};">{val}</div><div class="kpi-lbl">{lbl}</div><div class="kpi-pct">{val/total*100:.1f}%</div></div>',unsafe_allow_html=True)

        st.markdown("<br>",unsafe_allow_html=True)
        c1,c2=st.columns(2)
        with c1:
            seg_c=df["segment"].value_counts().reset_index()
            seg_c.columns=["Segment","Nombre"]
            fig1=px.pie(seg_c,values="Nombre",names="Segment",
                        color="Segment",color_discrete_map=COLORS,hole=0.45)
            fig1.update_traces(textposition='inside',textinfo='percent+label')
            fig1.update_layout(height=360,paper_bgcolor='rgba(0,0,0,0)',
                               plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig1,use_container_width=True)
        with c2:
            ss_c=df["sous_segment"].value_counts().head(10).reset_index()
            ss_c.columns=["Sous-segment","Nombre"]
            fig2=px.bar(ss_c,x="Nombre",y="Sous-segment",orientation="h",
                        color="Nombre",
                        color_continuous_scale=[BIAT_BLUE_LIGHT, BIAT_BLUE])
            fig2.update_layout(height=360,paper_bgcolor='rgba(0,0,0,0)',
                               yaxis=dict(autorange="reversed"),coloraxis_showscale=False)
            st.plotly_chart(fig2,use_container_width=True)

        cols=[c for c in ["id_client","marche_input","forme_juridique","age","mmm","vrd",
                           "nb_operations_12m","segment","sous_segment"] if c in df.columns]
        st.dataframe(df[cols].head(50),use_container_width=True,height=260)

        output=BytesIO()
        with pd.ExcelWriter(output,engine='openpyxl') as w:
            df.to_excel(w,index=False,sheet_name="Résultats")
            df.groupby(["segment","sous_segment"]).size().reset_index(name="Nombre").to_excel(w,index=False,sheet_name="Résumé")
            if n_dorm>0 and "nb_operations_12m" in df.columns:
                df[df["nb_operations_12m"]==0][cols].to_excel(w,index=False,sheet_name="Dormants ⚠️")
        st.download_button("⬇️ Télécharger Excel (Résultats + Résumé + Dormants)",
                           output.getvalue(),"resultats_segmentation_biat.xlsx",use_container_width=True)

# ─────────────────────────────────────────────────────────────────────
# PAGE 3 — SENSIBILITÉ
# ─────────────────────────────────────────────────────────────────────
def page_sensibilite():
    st.markdown(f'<div class="section-titre">📈 Analyse de sensibilité</div>', unsafe_allow_html=True)
    st.caption("Visualisez l'impact d'une modification de seuil sur la distribution des segments.")
    st.markdown("---")

    st.markdown(f"""
    <div class="info-biat">
        💡 L'analyse de sensibilité permet de simuler l'effet d'un changement de seuil
        (ex: baisser l'âge minimum Affluent de 30 à 25 ans) sur la distribution
        de votre portefeuille clients avant de l'appliquer officiellement.
    </div>""", unsafe_allow_html=True)

    c1,c2=st.columns(2)
    with c1:
        var=st.selectbox("Variable à analyser",["MMM (Affluent)","VRD (Affluent min)","Âge (Affluent)","MMM (TRE Premium)","VRD (ENR Premium)"])
    with c2:
        n=st.slider("Nb clients simulés",100,1000,300,100)

    P = st.session_state.get("params", DEFAUTS.copy())
    if st.button("🔬 Lancer l'analyse de sensibilité",type="primary",use_container_width=True):
        df=generer_demo(n)
        config = {
            "MMM (Affluent)":         ([0.5,1.0,2.0,3.0,4.0,5.0,6.0,8.0],"mmm_affluent","Seuil MMM Affluent (mD)"),
            "VRD (Affluent min)":     ([50,75,100,125,150,200,250],"vrd_aff_min","Seuil VRD Affluent min (mD)"),
            "Âge (Affluent)":         ([22,25,28,30,32,35,40],"age_affluent","Âge minimum Affluent (ans)"),
            "MMM (TRE Premium)":      ([10,15,20,25,30,35,40],"mmm_tre_p","Seuil MMM TRE Premium (mD)"),
            "VRD (ENR Premium)":      ([30,40,50,60,70,80,100],"vrd_enr_p","Seuil VRD ENR Premium (mD)"),
        }
        seuils,pk,label=config[var]
        resultats=[]
        for s in seuils:
            P_t=P.copy(); P_t[pk]=s; st.session_state["params"]=P_t
            segs=pd.Series([segmenter_client(r.to_dict())["segment"] for _,r in df.iterrows()])
            for seg,cnt in segs.value_counts().items():
                resultats.append({"Seuil":s,"Segment":seg,"% clients":cnt/n*100})
        st.session_state["params"]=P

        df_r=pd.DataFrame(resultats)
        fig=px.line(df_r,x="Seuil",y="% clients",color="Segment",
                    color_discrete_map=COLORS,markers=True,
                    labels={"Seuil":label},
                    title=f"Sensibilité de la distribution — {label}")
        fig.update_layout(height=440,paper_bgcolor='rgba(0,0,0,0)',
                          yaxis=dict(range=[0,100]),
                          plot_bgcolor=BIAT_GRAY)
        fig.update_xaxes(gridcolor="#e2e8f0")
        fig.update_yaxes(gridcolor="#e2e8f0")
        st.plotly_chart(fig,use_container_width=True)

        pivot=df_r.pivot_table(index="Seuil",columns="Segment",values="% clients",fill_value=0).round(1)
        st.dataframe(pivot,use_container_width=True)

# ─────────────────────────────────────────────────────────────────────
# PAGE 4 — RÉFÉRENTIEL
# ─────────────────────────────────────────────────────────────────────
def page_referentiel():
    P = st.session_state["params"]
    st.markdown(f'<div class="section-titre">📋 Référentiel officiel des règles</div>', unsafe_allow_html=True)
    st.caption("Source : Note PBD N°2023-06 — BIAT · Direction Marketing et Développement Digital")
    st.markdown("---")

    choix=st.radio("Marché",["👤 Particuliers (PART)","💼 Professionnels (PRO)","🌍 TRE","🌐 ENR"],horizontal=True)

    if "PART" in choix:
        secs=[
            (f"🏆 Haut de Gamme — PART",COLORS["Haut de Gamme"],[
                ("Fortunés",              f"Particulier · VRD ≥ {P['vrd_fortunes']} mD"),
                ("Patrimoniaux",           f"Particulier · VRD ∈ [{P['vrd_pat_min']},{P['vrd_pat_max']}[ mD"),
                ("Affluent",               f"Particulier · âge ≥ {P['age_affluent']} ans · MMM ≥ {P['mmm_affluent']} mD OU VRD ∈ [{P['vrd_aff_min']},{P['vrd_aff_max']}[ mD"),
                ("Professions Libérales HG",f"Particulier · Prof. libérale (Annexe 5) · VRD ∈ [{P['vrd_lib_min']},{P['vrd_lib_max']}[ mD"),
                ("Épargnants HG",           f"Particulier · MMM = 0 · VRD ∈ [{P['vrd_ep_hg']},{P['vrd_aff_max']}[ mD"),
            ]),
            (f"🟢 Classe Moyenne — PART",COLORS["Classe Moyenne"],[
                ("Les Salariés",           f"Particulier · âge ≥ {P['age_cm']} ans · MMM ∈ [{P['mmm_sal_min']},{P['mmm_sal_max']}[ OU VRD ∈ [{P['vrd_sal_min']},{P['vrd_sal_max']}[ mD"),
                ("Épargnants CM",           f"Particulier · MMM = 0 · VRD ∈ [{P['vrd_ep_cm_min']},{P['vrd_ep_cm_max']}[ mD"),
            ]),
            (f"🔵 Grand Public — PART",COLORS["Grand Public"],[
                ("Particuliers",           "MMM < 1 mD · VRD < 5 mD"),
                ("Clients dormants",       "nb_operations_12m = 0 → détection automatique ⚠️"),
            ]),
            (f"🟣 Les Jeunes — PART",COLORS["Les Jeunes"],[
                ("Enfants et Élèves",      f"Âge ≤ {P['age_enfants']} ans"),
                ("Étudiants",              f"Âge ≤ {P['age_jeunes']} ans · Étudiant"),
                ("JDA Potentiel",          f"Âge ≤ {P['age_jeunes']} ans · Profession à potentiel (Annexe 4)"),
                ("Autres JDA",             f"Âge ≤ {P['age_jeunes']} ans · Autres professions"),
            ]),
        ]
    elif "PRO" in choix:
        secs=[
            (f"🏆 Haut de Gamme — PRO",COLORS["Haut de Gamme"],[
                ("Professionnels HG",      f"Professionnel · Profession à potentiel (Annexe 4) · VRD ≥ {P['vrd_pro_hg']} mD"),
                ("Patrimoniaux PRO",       f"Professionnel · VRD ≥ {P['vrd_pro_pat_min']} mD"),
                ("Professions Libérales HG",f"Professionnel · Prof. libérale · VRD ∈ [{P['vrd_lib_min']},{P['vrd_lib_max']}[ mD"),
                ("Épargnants PRO HG",      f"Professionnel · MMM = 0 · VRD ∈ [{P['vrd_ep_hg']},{P['vrd_aff_max']}[ mD"),
            ]),
            (f"🟢 Classe Moyenne — PRO",COLORS["Classe Moyenne"],[
                ("Commerçants & Artisans CM",f"Professionnel · MMM ∈ [{P['mmm_pro_cm_min']},{P['mmm_pro_cm_max']}[ mD"),
                ("Épargnants PRO CM",        f"Professionnel · MMM = 0 · VRD ∈ [{P['vrd_ep_cm_min']},{P['vrd_ep_cm_max']}[ mD"),
            ]),
            (f"🔵 Grand Public — PRO",COLORS["Grand Public"],[
                ("Commerçants & Artisans GP",f"Professionnel · MMM < {P['mmm_pro_cm_min']} mD"),
                ("Clients dormants PRO",    "nb_operations_12m = 0 → détection automatique ⚠️"),
            ]),
        ]
    elif "TRE" in choix:
        secs=[(f"🌍 TRE",COLORS["TRE"],[
            ("Premium",         f"Profession à potentiel OU MMM ≥ {P['mmm_tre_p']} mD OU VRD ≥ {P['vrd_tre_p']} mD"),
            ("Potentiel moyen", f"MMM ∈ [{P['mmm_tre_m_min']},{P['mmm_tre_m_max']}[ mD OU VRD ∈ [{P['vrd_tre_m_min']},{P['vrd_tre_m_max']}[ mD"),
            ("Faible potentiel","MMM faible ET VRD faible · compte actif"),
            ("TRE Inactif",     "nb_operations_12m = 0 → détection automatique ⚠️"),
        ])]
    else:
        secs=[(f"🌐 ENR",COLORS["ENR"],[
            ("Premium",         f"MMM ≥ {P['mmm_enr_p']} mD OU VRD ≥ {P['vrd_enr_p']} mD"),
            ("Potentiel moyen", f"MMM ∈ [{P['mmm_enr_m_min']},{P['mmm_enr_m_max']}[ mD OU VRD ∈ [{P['vrd_enr_m_min']},{P['vrd_enr_m_max']}[ mD"),
            ("Faible potentiel","MMM faible ET VRD faible · compte actif"),
            ("ENR Inactif",     "nb_operations_12m = 0 → détection automatique ⚠️"),
        ])]

    for titre,couleur,sous_segs in secs:
        with st.expander(titre,expanded=True):
            for nom,critere in sous_segs:
                st.markdown(f"""
                <div style="border-left:4px solid {couleur};padding:9px 14px;
                            margin:5px 0;background:{BIAT_GRAY};border-radius:0 8px 8px 0;">
                    <strong style="color:{BIAT_BLUE};">{nom}</strong><br>
                    <span style="color:{BIAT_GRAY_DARK};font-size:.87rem;">📏 {critere}</span>
                </div>""",unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────
# PAGE 5 — CHATBOT
# ─────────────────────────────────────────────────────────────────────
def page_chatbot():
    st.markdown(f'<div class="section-titre">🤖 BIATBot — Assistant de segmentation</div>', unsafe_allow_html=True)
    st.caption("Posez vos questions sur les segments, variables, marchés et fonctionnalités du simulateur.")
    st.markdown("---")

    # Affichage de l'historique des messages
    chat_html = '<div class="chat-box">'
    for msg in st.session_state["chat"]:
        if msg["r"] == "user":
            chat_html += f'<div class="msg-user"><div class="msg-nom-usr">Vous</div>{msg["m"]}</div>'
        else:
            chat_html += f'<div class="msg-bot"><div class="msg-nom-bot">🤖 BIATBot</div>{msg["m"]}</div>'
    chat_html += '</div>'
    st.markdown(chat_html, unsafe_allow_html=True)

    st.markdown("**💡 Questions fréquentes :**")
    c1, c2, c3 = st.columns(3)
    sugs = [
        "C'est quoi le MMM ?", "C'est quoi le VRD ?", "C'est quoi mD ?",
        "Différence PART et PRO ?", "C'est quoi un dormant ?", "C'est quoi un JDA ?",
        "C'est quoi le Haut de Gamme ?", "Couleurs officielles BIAT ?", "Comment imprimer ?"
    ]
    
    for i, q in enumerate(sugs):
        col = [c1, c2, c3][i % 3]
        if col.button(q, key=f"s{i}", use_container_width=True):
            st.session_state["chat"].append({"r": "user", "m": q})
            st.session_state["chat"].append({"r": "bot", "m": repondre(q)})
            st.rerun()

    st.markdown("---")

    # Formulaire d'envoi de message (doit être indenté à l'intérieur de la fonction)
    with st.form(key="chat_form_unique", clear_on_submit=True):
        ci, cb = st.columns([5, 1])
        with ci:
            user_input = st.text_input(
                "Votre question",
                placeholder="Ex: C'est quoi l'Affluent ?",
                label_visibility="collapsed"
            )
        with cb:
            send = st.form_submit_button("📤 Envoyer", use_container_width=True)

        if send and user_input.strip():
            st.session_state["chat"].append({"r": "user", "m": user_input})
            st.session_state["chat"].append({"r": "bot", "m": repondre(user_input)})
            st.rerun()

    # Bouton pour effacer (indenté aussi)
    if st.button("🗑️ Effacer la conversation"):
        st.session_state["chat"] = [{"r": "bot", "m": "Bonjour ! 👋 Je suis **BIATBot**. Comment puis-je vous aider ?"}]
        st.rerun()
# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────
def main():
    # ── Header avec logo BIAT ──────────────────────────────────────
    st.markdown(f"""
    <div class="biat-header">
        <div class="biat-header-top">
            <img src="data:image/svg+xml;base64,{LOGO_B64}" width="170" alt="BIAT Logo">
            <div>
                <div class="biat-header-title">Simulateur de Segmentation Clientèle</div>
                <div class="biat-header-sub">Pôle Banque de Détail &nbsp;·&nbsp; PART · PRO · TRE · ENR</div>
                <div class="biat-header-sub" style="margin-top:2px;">Note PBD N°2023-06 &nbsp;·&nbsp; <span class="biat-version">v5.0</span></div>
            </div>
        </div>
        <div class="biat-header-bar"></div>
    </div>
    """, unsafe_allow_html=True)

    render_sidebar()

    tabs = st.tabs([
        "🔍 Simulation individuelle",
        "📊 Simulation en masse",
        "📈 Analyse de sensibilité",
        "📋 Référentiel",
        "🤖 BIATBot",
    ])

    with tabs[0]: page_individuelle()
    with tabs[1]: page_masse()
    with tabs[2]: page_sensibilite()
    with tabs[3]: page_referentiel()
    with tabs[4]: page_chatbot()

    # Footer
    st.markdown(f"""
    <div class="biat-footer">
        🏦 &nbsp;<strong>BIAT</strong> — Banque Internationale Arabe de Tunisie &nbsp;|&nbsp;
        Pôle Banque de Détail · Direction Marketing et Développement Digital &nbsp;|&nbsp;
        Simulateur de Segmentation v5.0 &nbsp;·&nbsp; Note PBD N°2023-06
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
