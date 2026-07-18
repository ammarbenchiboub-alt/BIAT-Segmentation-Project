"""
=====================================================================
 APPLICATION BIAT - Simulation de segmentation client (Note 2023-06)
=====================================================================
Point d'entree Streamlit. Toutes les fonctionnalites (simulateur, import
CSV, chatbot, assistant IA) s'appuient sur le MOTEUR UNIQUE (core.engine).

Lancer :  streamlit run app.py
"""
from __future__ import annotations

import copy
import json

import pandas as pd
import streamlit as st

from core import MoteurSegmentation
from core.rules_loader import CHEMIN_REGLES, empreinte_regles
from chatbot import ChatbotExpert
from assistant import AssistantIA
from segmentation import segmenter_dataframe
from templates import generer_template_excel
from validation import VALEURS_MARCHE, VALEURS_RESIDENCE, VALEURS_NATIONALITE, selectionner_feuille
from dashboard import calculer_kpis, repartition, calculer_kpis_ml, repartition_scores_confiance
from ui import (
    injecter_css, entete_biat, carte_segment, section, kpi, legende_segments, COULEURS,
    masthead, sidebar_brand,
)
from core.ml_anomaly import analyser_anomalie, analyser_dataframe, infos_modele, reentrainer_modele
from auth import authentifier
from audit import enregistrer as enregistrer_audit, enregistrer_lot as enregistrer_audit_lot
from audit import lister as lister_audit, compter as compter_audit, verifier_integrite as verifier_integrite_audit
from audit import lister_profils as lister_profils_audit
from gouvernance import (
    proposer as proposer_changement, lister_en_attente as lister_propositions_en_attente,
    lister_historique as lister_historique_propositions,
    rejeter as rejeter_proposition, simuler_impact,
    assurer_version_initiale, lister_versions, charger_version,
    appliquer_proposition,
)

st.set_page_config(page_title="BIAT - Segmentation client", page_icon="🏦", layout="wide")
injecter_css()


# --------------------------------------------------------------------------- #
# Authentification (compte local + role : conseiller / admin / auditeur)
# --------------------------------------------------------------------------- #
if "auth" not in st.session_state:
    st.session_state.auth = None

if st.session_state.auth is None:
    masthead()
    section("Connexion")
    _, col_form, _ = st.columns([1, 1.3, 1])
    with col_form:
        with st.form("form_connexion"):
            _identifiant = st.text_input("Identifiant")
            _mdp = st.text_input("Mot de passe", type="password")
            _valide = st.form_submit_button("Se connecter", use_container_width=True)
        if _valide:
            # authentifier() (et non verifier_identifiants()) : integre la
            # protection contre les attaques par force brute -- verrouillage
            # temporaire du compte apres N echecs, deverrouillage automatique,
            # et journalisation des tentatives. Voir auth/tentatives.py.
            _resultat = authentifier(_identifiant, _mdp)
            if _resultat["succes"]:
                st.session_state.auth = _resultat["utilisateur"]
                st.rerun()
            elif _resultat["verrouille"]:
                # Compte verrouille : on affiche le temps restant exact.
                st.error(f"🔒 {_resultat['message']}")
            else:
                st.error(_resultat["message"])
        st.caption(
            "Comptes de demonstration (PFE) : conseiller1 / admin1 / admin2 / auditeur1 "
            "-- mots de passe dans le README (admin1 et admin2 permettent de tester la "
            "double validation des seuils : l'un propose, l'autre confirme)."
        )
    st.stop()


# --------------------------------------------------------------------------- #
# Cache du moteur unique
# --------------------------------------------------------------------------- #
# Streamlit reexecute TOUT ce script a chaque interaction (clic, saisie...).
# Sans cache, chaque rerun relisait et reparsait regles_segmentation.json puis
# reconstruisait le moteur, le chatbot et l'assistant -- un travail identique
# repete des dizaines de fois par session.
#
# La clef de cache est l'EMPREINTE DU CONTENU du fichier de regles :
#   - tant que les regles ne changent pas, l'empreinte est stable et la meme
#     instance de moteur est reutilisee a chaque rerun ;
#   - des qu'une proposition est appliquee (page Parametrage), le contenu du
#     fichier change, donc l'empreinte change, donc Streamlit reconstruit
#     automatiquement le moteur avec les nouveaux seuils.
# L'invalidation est ainsi exacte : ni cache perime, ni reconstruction inutile.
# Aucun appel manuel a .clear() n'est necessaire, ce qui supprime le risque
# d'oublier d'invalider le cache lors d'une evolution future.
#
# Le parametre `empreinte` n'est pas utilise dans le corps de la fonction :
# il ne sert qu'a faire partie de la clef de cache. C'est le mecanisme standard
# de @st.cache_resource.
@st.cache_resource(show_spinner=False)
def _construire_moteur(empreinte: str) -> MoteurSegmentation:
    return MoteurSegmentation()


@st.cache_resource(show_spinner=False)
def _construire_chatbot(empreinte: str) -> ChatbotExpert:
    return ChatbotExpert(_construire_moteur(empreinte))


@st.cache_resource(show_spinner=False)
def _construire_assistant(empreinte: str) -> AssistantIA:
    return AssistantIA(_construire_moteur(empreinte))


def get_moteur() -> MoteurSegmentation:
    """Renvoie l'instance unique du moteur pour les regles actuellement en
    vigueur. API inchangee : les appelants existants n'ont rien a modifier."""
    return _construire_moteur(empreinte_regles())


if "historique" not in st.session_state:
    st.session_state.historique = pd.DataFrame()

_EMPREINTE_REGLES = empreinte_regles()
moteur = _construire_moteur(_EMPREINTE_REGLES)
chatbot = _construire_chatbot(_EMPREINTE_REGLES)
assistant = _construire_assistant(_EMPREINTE_REGLES)


def ajouter_historique(lignes: list[dict]) -> None:
    if not lignes:
        return
    st.session_state.historique = pd.concat(
        [st.session_state.historique, pd.DataFrame(lignes)], ignore_index=True
    )


# --------------------------------------------------------------------------- #
# Barre laterale
# --------------------------------------------------------------------------- #
_ROLE = st.session_state.auth["role"]

_PAGES = ["Accueil", "Simulation individuelle", "Import CSV",
          "Chatbot Expert", "Tableau de bord", "Parametrage"]
_ICONES_PAGES = {
    "Accueil": "🏠", "Simulation individuelle": "🧮", "Import CSV": "📂",
    "Chatbot Expert": "💬", "Tableau de bord": "📊", "Parametrage": "⚙️",
    "Journal d'audit": "🛡️",
}
if _ROLE != "admin":
    # Parametrage des seuils reserve au role admin (modification des regles
    # officielles) : un conseiller ou un auditeur ne doit pas pouvoir y acceder.
    _PAGES = [p for p in _PAGES if p != "Parametrage"]
if _ROLE not in ("admin", "auditeur"):
    # Journal d'audit reserve aux roles admin et auditeur (tracabilite /
    # controle interne) : un conseiller ne doit pas pouvoir consulter les
    # decisions des autres conseillers.
    _PAGES = [p for p in _PAGES if p != "Journal d'audit"]
else:
    _PAGES = _PAGES + ["Journal d'audit"]

if "nav_page" not in st.session_state:
    st.session_state.nav_page = "Accueil"
if st.session_state.nav_page not in _PAGES:
    # Ex : role different apres reconnexion, page devenue inaccessible.
    st.session_state.nav_page = "Accueil"
if "nav_historique" not in st.session_state:
    st.session_state.nav_historique = []
if "_derniere_page_connue" not in st.session_state:
    st.session_state._derniere_page_connue = st.session_state.nav_page

# Applique une navigation demandee par un clic (carte Accueil, bouton Retour)
# AVANT de creer le widget radio ci-dessous : Streamlit interdit de modifier
# st.session_state["nav_page"] apres l'instanciation du widget "nav_page".
if "_nav_demandee" in st.session_state:
    _cible = st.session_state.pop("_nav_demandee")
    _est_retour = st.session_state.pop("_nav_est_retour", False)
    st.session_state.nav_page = _cible
    if _est_retour:
        # Navigation via le bouton Retour : on ne ré-empile pas la page quittee.
        st.session_state._derniere_page_connue = _cible

with st.sidebar:
    sidebar_brand()
    st.caption(f"👤 {st.session_state.auth['nom']} · role : {_ROLE}")
    if st.button("Se deconnecter", use_container_width=True, key="btn_deconnexion"):
        st.session_state.auth = None
        st.rerun()
    st.markdown("---")
    page = st.radio(
        "Navigation",
        _PAGES,
        format_func=lambda p: f"{_ICONES_PAGES.get(p, '')}  {p}",
        label_visibility="collapsed",
        key="nav_page",
    )
    st.markdown("---")
    st.caption("Source unique : Note BIAT 2023-06")
    st.caption(f"Simulations en session : {len(st.session_state.historique)}")

# Empile la page quittee des qu'un changement de page est detecte (carte,
# bouton Retour ou clic direct dans le menu lateral).
if page != st.session_state._derniere_page_connue:
    st.session_state.nav_historique.append(st.session_state._derniere_page_connue)
    st.session_state._derniere_page_connue = page

if page != "Accueil" and st.session_state.nav_historique:
    col_retour, _ = st.columns([1, 6])
    with col_retour:
        _cible_retour = st.session_state.nav_historique[-1]
        if st.button("← Retour", key="btn_retour", help=f"Revenir à « {_cible_retour} »"):
            st.session_state.nav_historique.pop()
            st.session_state._nav_demandee = _cible_retour
            st.session_state._nav_est_retour = True
            st.rerun()


# --------------------------------------------------------------------------- #
# Accueil
# --------------------------------------------------------------------------- #
if page == "Accueil":
    masthead()
    st.markdown(
        "Cette application reproduit le moteur de segmentation de la clientele PBD "
        "de la BIAT. Un **moteur unique** applique strictement les regles de la note "
        "officielle. La condition entre **MMM et VRD** est un **OU** (jamais un ET)."
    )
    section("Fonctionnalites")
    c1, c2, c3, c4 = st.columns(4)
    fonctions = [
        (c1, "🧮", "Simulation individuelle", "Segmenter un client a partir de 7 champs metier."),
        (c2, "📂", "Import CSV", "Segmenter un fichier complet en masse avec controle des erreurs."),
        (c3, "💬", "Chatbot Expert", "Interroger la note et analyser un profil client."),
        (c4, "📊", "Tableau de bord", "Suivre les indicateurs et la repartition par segment."),
    ]
    for col, icone, titre, txt in fonctions:
        with col:
            with st.container(border=True):
                st.markdown(f'<div class="nav-card-icon">{icone}</div>', unsafe_allow_html=True)
                st.markdown(f"**{titre}**")
                st.caption(txt)
                if st.button("Ouvrir →", key=f"nav_card_{titre}", use_container_width=True):
                    st.session_state._nav_demandee = titre
                    st.rerun()
    st.markdown("")
    section("Perimetre")
    st.info("Marches geres : PART, PRO, TRE, ENR. Le marche TPME n'est pas gere.")
    legende_segments(["Haut de Gamme", "Classe Moyenne", "Grand Public", "Les Jeunes",
                      "Premium", "Potentiel moyen", "Faible potentiel"])


# --------------------------------------------------------------------------- #
# Simulation individuelle
# --------------------------------------------------------------------------- #
elif page == "Simulation individuelle":
    entete_biat("Simulation individuelle", "Segmentation d'un client via le moteur unique")

    professions = ["Autre", "Etudiant", "Commercant", "Artisan"] + moteur.professions_connues()
    professions = list(dict.fromkeys(professions))

    with st.form("form_sim"):
        section("Profil client")
        c1, c2, c3 = st.columns(3)
        with c1:
            marche = st.selectbox("Marche", VALEURS_MARCHE)
            profession = st.selectbox("Profession", professions)
        with c2:
            age = st.number_input("Age", min_value=0, max_value=120, value=40, step=1)
            nationalite = st.selectbox("Nationalite", VALEURS_NATIONALITE)
        with c3:
            residence = st.selectbox("Residence", VALEURS_RESIDENCE)
        c4, c5 = st.columns(2)
        with c4:
            mmm = st.number_input("MMM - Mouvements mensuels moyens (DT)", min_value=0.0, value=0.0, step=100.0, format="%.2f")
        with c5:
            vrd = st.number_input("VRD - Total des avoirs stables (DT)", min_value=0.0, value=0.0, step=100.0, format="%.2f")
        epargnant_exclusif = st.checkbox(
            "Ce client detient-il uniquement des comptes Epargne / Depots a terme "
            "(pas de compte courant) ?",
            value=False,
            help="Champ optionnel (8e champ). Active, pour le marche PART, le sous-segment "
                 "'Epargnants et deposants exclusifs' (Affluent / Classe Moyenne / Grand Public) "
                 "quand les montants correspondent.",
        )
        soumis = st.form_submit_button("Segmenter le client")

    if soumis:
        profil = {"Marche": marche, "Profession": profession, "Age": int(age),
                  "MMM": mmm, "VRD": vrd, "Nationalite": nationalite, "Residence": residence,
                  "EpargnantDeposantExclusif": epargnant_exclusif}
        res = moteur.segmenter(profil)
        analyse = assistant.analyser(res)
        analyse_ml = analyser_anomalie(profil)
        enregistrer_audit(
            "SIMULATION_INDIVIDUELLE", st.session_state.auth, profil,
            res.segment, res.sous_segment, res.regle_id,
        )

        if mmm == 0 and vrd == 0:
            st.warning(
                "⚠️ MMM et VRD sont tous les deux a 0. Si ce n'est pas un oubli de saisie, le "
                "resultat ci-dessous est correct (un client sans MMM ni VRD releve du palier le "
                "plus bas). Sinon, verifiez les montants avant de valider ce resultat."
            )

        gauche, droite = st.columns([1, 1])
        with gauche:
            section("Resultat de la segmentation")
            carte_segment(res.segment, res.sous_segment, res.regle_id)
            with st.expander("Detail de l'evaluation (moteur)"):
                for e in res.explications:
                    st.text(e)

        with droite:
            niveau = analyse["niveau"]
            badge = {"Eleve": "badge-ok", "Moyen": "badge-warn", "Faible": "badge-bad"}[niveau]
            st.markdown(
                f'<div class="section-title">🤖 Assistant IA '
                f'<span class="badge {badge}">Confiance {analyse["score_confiance"]} % - {niveau}</span></div>',
                unsafe_allow_html=True,
            )
            if analyse["alertes"]:
                for a in analyse["alertes"]:
                    st.warning(a)
            if analyse["recommandations"]:
                st.markdown("**Recommandations**")
                for r in analyse["recommandations"]:
                    st.markdown(f"- {r}")
            if analyse["coherences"]:
                with st.expander("Controles de coherence"):
                    for c in analyse["coherences"]:
                        st.markdown(f"- {c}")
            st.caption("L'assistant IA ne modifie jamais le segment calcule par le moteur.")

        st.markdown("")
        niveau_ml = analyse_ml["niveau"]
        badge_ml = {"Normal": "badge-ok", "Atypique": "badge-warn", "Incoherent": "badge-bad"}[niveau_ml]
        st.markdown(
            f'<div class="section-title">🧠 Analyse Machine Learning (detection d\'anomalies) '
            f'<span class="badge {badge_ml}">{analyse_ml["emoji"]} {niveau_ml} - '
            f'Confiance {analyse_ml["score_confiance"]} %</span></div>',
            unsafe_allow_html=True,
        )
        for e in analyse_ml["explications"]:
            if niveau_ml == "Normal":
                st.caption(e)
            else:
                st.warning(e)
        st.caption(
            "Modele Isolation Forest (scikit-learn), entraine sur des profils simules a partir des "
            "paliers de la note. Analyse statistique complementaire : ne modifie jamais le segment "
            "calcule par le moteur metier."
        )

        ajouter_historique([{**profil, "Segment": res.segment or "-",
                             "Sous_segment": res.sous_segment or "-",
                             "Regle": res.regle_id or "-",
                             "Statut": "Segmente" if res.succes else "Non segmente",
                             "Confiance": analyse["score_confiance"],
                             "ML_Anomalie": analyse_ml["anomalie"],
                             "ML_Confiance": analyse_ml["score_confiance"],
                             "ML_Niveau": analyse_ml["niveau"]}])


# --------------------------------------------------------------------------- #
# Import CSV
# --------------------------------------------------------------------------- #
elif page == "Import CSV":
    entete_biat("Import CSV en masse", "Validation, segmentation et export")

    section("1. Telecharger le modele")
    st.download_button("Modele Excel (.xlsx) avec listes deroulantes", data=generer_template_excel(),
                       file_name="modele_import_biat.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    section("2. Importer un fichier")
    fichier = st.file_uploader("Fichier CSV ou Excel a segmenter", type=["csv", "xlsx"])
    st.caption(
        "Glissez-deposez un fichier CSV ou Excel (.xlsx), ou cliquez sur « Browse files ». "
        "Taille maximale : 200 Mo. Pour un fichier Excel a plusieurs feuilles, celle qui "
        "contient les colonnes attendues (Marche, Age, MMM, VRD...) est detectee automatiquement."
    )

    if fichier is not None:
        try:
            if fichier.name.lower().endswith(".xlsx"):
                # sheet_name=None : lit TOUTES les feuilles, puis on retient
                # celle qui contient les colonnes a segmenter (une feuille de
                # notice ou de listes de reference peut preceder les donnees).
                feuilles = pd.read_excel(fichier, sheet_name=None)
                df_in = selectionner_feuille(feuilles)
            else:
                df_in = pd.read_csv(fichier)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Lecture impossible : {exc}")
            df_in = None

        if df_in is not None:
            section("3. Apercu du fichier")
            st.dataframe(df_in.head(), use_container_width=True)

            resultats, invalides = segmenter_dataframe(df_in, moteur)

            if not resultats.empty:
                resultats = pd.concat([resultats, analyser_dataframe(resultats)], axis=1)

            # Journal d'audit : une entree par ligne segmentee, comme pour la
            # simulation individuelle. Garde-fou anti-doublon : ce bloc se
            # reexecute a chaque interaction Streamlit (ex: clic sur un autre
            # bouton) tant que le meme fichier reste charge ; on ne
            # rejournalise donc que si le fichier importe a change.
            _cle_import = f"{fichier.name}:{fichier.size}:{len(resultats)}"
            if not resultats.empty and st.session_state.get("_dernier_import_journalise") != _cle_import:
                enregistrer_audit_lot("IMPORT_MASSE", st.session_state.auth, resultats.to_dict("records"))
                st.session_state["_dernier_import_journalise"] = _cle_import

            section("4. Synthese du controle")
            k1, k2, k3, k4 = st.columns(4)
            with k1:
                kpi("Lignes lues", len(df_in), icone="📄")
            with k2:
                kpi("Segmentees", len(resultats), "lignes valides", icone="✅")
            with k3:
                kpi("Invalides", len(invalides), "a corriger", icone="⚠️")
            with k4:
                nb_anomalies = int(resultats["ML_Anomalie"].sum()) if "ML_Anomalie" in resultats else 0
                kpi("Anomalies ML", nb_anomalies, "profils atypiques (Isolation Forest)", icone="🧠")

            if not invalides.empty:
                section("Lignes invalides")
                st.dataframe(invalides, use_container_width=True)

            if not resultats.empty:
                section("Resultats de la segmentation")
                st.caption(
                    "Colonnes ML_Anomalie / ML_Confiance / ML_Niveau : analyse Machine Learning "
                    "(Isolation Forest) complementaire, sans impact sur Segment / Sous_segment."
                )
                st.dataframe(resultats, use_container_width=True)
                st.download_button(
                    "Telecharger les resultats (CSV)",
                    data=resultats.to_csv(index=False).encode("utf-8"),
                    file_name="resultats_segmentation.csv", mime="text/csv",
                )
                if st.button("Ajouter au tableau de bord"):
                    ajouter_historique(resultats.to_dict("records"))
                    st.success(f"{len(resultats)} lignes ajoutees au tableau de bord.")


# --------------------------------------------------------------------------- #
# Chatbot Expert
# --------------------------------------------------------------------------- #
elif page == "Chatbot Expert":
    entete_biat("Chatbot Expert metier", "Repond a partir de la note et du moteur unique")

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "Bonjour. Posez une question sur la segmentation, "
             "ou decrivez un profil (Marche, Age, MMM, VRD, Profession...) pour une aide a la decision."}
        ]

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    with st.expander("Exemples de questions"):
        st.markdown(
            "- Quelle est la logique entre MMM et VRD ?\n"
            "- Quels sont les seuils du segment Affluent ?\n"
            "- Liste des professions liberales ?\n"
            "- Marche = PRO Profession = Commercant Age = 40 MMM = 90 VRD = 3"
        )

    question = st.chat_input("Votre question...")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        rep = chatbot.repondre(question)
        contenu = rep["reponse"]
        if rep.get("source"):
            contenu += f"\n\n_Source : {rep['source']}_"
        with st.chat_message("assistant"):
            st.markdown(contenu)
        st.session_state.messages.append({"role": "assistant", "content": contenu})


# --------------------------------------------------------------------------- #
# Tableau de bord
# --------------------------------------------------------------------------- #
elif page == "Tableau de bord":
    entete_biat("Tableau de bord", "Indicateurs de pilotage de la session")
    df = st.session_state.historique

    if df.empty:
        st.info("Aucune donnee pour le moment. Lancez des simulations ou importez un fichier CSV "
                "puis cliquez sur 'Ajouter au tableau de bord'.")
    else:
        k = calculer_kpis(df)
        section("Indicateurs cles")
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            kpi("Simulations realisees", k["total"], "clients evalues", icone="👥")
        with c2:
            kpi("Taux de segmentation", k["taux_segmentation"], f'{k["segmentes"]} clients classes', icone="🎯")
        with c3:
            kpi("Segment dominant", k["segment_dominant"], f'{k["part_dominant"]} des clients' if k["part_dominant"] else "", icone="🏆")
        with c4:
            kpi("Part Haut de Gamme / Premium", k["part_haut_gamme"], "clients a fort potentiel", icone="💎")
        with c5:
            kpi("Confiance moyenne (IA)", k["confiance_moyenne"], "fiabilite des resultats", icone="🤖")

        st.markdown("")
        section("Repartition")
        legende_segments([s for s in COULEURS if s != "-"])
        g1, g2 = st.columns(2)
        with g1:
            st.caption("Par segment")
            st.bar_chart(repartition(df, "Segment").set_index("Segment"))
        with g2:
            st.caption("Par marche")
            st.bar_chart(repartition(df, "Marche").set_index("Marche"))

        section("Detail par sous-segment")
        st.dataframe(repartition(df, "Sous_segment"), use_container_width=True)

        section("🧠 Analyse Machine Learning (detection d'anomalies)")
        k_ml = calculer_kpis_ml(df)
        if not k_ml["disponible"]:
            st.info("Aucune analyse Machine Learning disponible pour le moment.")
        else:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                kpi("Profils analyses (ML)", k_ml["total"], icone="🔍")
            with m2:
                kpi("Anomalies detectees", k_ml["anomalies"], icone="🚨")
            with m3:
                kpi("Taux d'anomalies", k_ml["taux_anomalies"], icone="📈")
            with m4:
                kpi("Confiance moyenne (ML)", k_ml["confiance_moyenne"], icone="🎯")
            gm1, gm2 = st.columns(2)
            with gm1:
                st.caption("Repartition des scores de confiance")
                st.bar_chart(repartition_scores_confiance(df).set_index("Tranche"))
            with gm2:
                st.caption("Anomalies detectees par marche")
                st.bar_chart(repartition(df[df["ML_Anomalie"] == True], "Marche").set_index("Marche"))  # noqa: E712
            st.caption(
                "Module complementaire (Isolation Forest, scikit-learn) : n'influence jamais le "
                "segment calcule par le moteur metier, qui reste l'unique source officielle."
            )
            with st.expander("⚙️ Modele Machine Learning"):
                meta = infos_modele()
                if meta:
                    st.caption(
                        f"Modele entraine le {meta.get('entraine_le', '-')} sur "
                        f"{meta.get('n_echantillons', '-')} profils simules."
                    )
                if st.button("Reentrainer le modele de detection d'anomalies"):
                    meta = reentrainer_modele()
                    st.success(
                        f"Modele reentraine le {meta['entraine_le']} sur {meta['n_echantillons']} "
                        f"profils simules."
                    )
                    st.rerun()

        with st.expander("Historique complet des segmentations"):
            st.dataframe(df, use_container_width=True)
        c_exp, c_clr = st.columns([1, 1])
        with c_exp:
            st.download_button("Exporter l'historique (CSV)",
                               data=df.to_csv(index=False).encode("utf-8"),
                               file_name="historique_segmentation.csv", mime="text/csv")
        with c_clr:
            if st.button("Vider l'historique"):
                st.session_state.historique = pd.DataFrame()
                st.rerun()


# --------------------------------------------------------------------------- #
# Parametrage
# --------------------------------------------------------------------------- #
elif page == "Parametrage":
    if _ROLE != "admin":
        # Defense en profondeur : la page n'est deja plus proposee dans le
        # menu pour ce role (cf. filtrage de _PAGES), mais on bloque aussi
        # l'acces direct au contenu par prudence.
        st.error("Acces reserve au role Administrateur.")
        st.stop()
    entete_biat("Parametrage des regles", "Simulation d'impact + double validation avant application")
    st.warning("Modification de la source unique de regles (regles_segmentation.json). "
               "Toute modification impacte l'ensemble des fonctionnalites. Aucun changement "
               "n'est applique directement : il doit d'abord etre propose, puis confirme par "
               "un SECOND administrateur.")

    with open(CHEMIN_REGLES, encoding="utf-8") as f:
        regles = json.load(f)
    assurer_version_initiale(regles)

    # ----------------------------------------------------------------- #
    # Propositions en attente (double validation / Maker-Checker)
    # ----------------------------------------------------------------- #
    section("Propositions en attente de confirmation")
    _en_attente = lister_propositions_en_attente()
    if not _en_attente:
        st.caption("Aucune proposition en attente.")
    for _p in _en_attente:
        with st.container(border=True):
            st.markdown(f"**Proposition #{_p['id']}** — {_p['nom_propose_par']} · {_p['horodatage_proposition']}")
            st.caption(_p["description"] or "(pas de justification fournie)")
            if _p["propose_par"] == st.session_state.auth["identifiant"]:
                st.info(
                    "En attente de confirmation par un AUTRE administrateur : vous ne pouvez "
                    "pas confirmer votre propre proposition (separation des taches)."
                )
                if st.button("Annuler ma proposition", key=f"annuler_{_p['id']}"):
                    rejeter_proposition(_p["id"], st.session_state.auth)
                    st.rerun()
            else:
                c_conf, c_rej = st.columns(2)
                with c_conf:
                    if st.button("✅ Confirmer et appliquer", key=f"confirmer_{_p['id']}", use_container_width=True):
                        # Operation TRANSACTIONNELLE : confirmation + ecriture des
                        # regles + versionnement + audit reussissent ensemble, ou
                        # sont toutes annulees. Auparavant ces quatre etapes
                        # etaient enchainees ici sans filet : une erreur au milieu
                        # laissait un etat incoherent (regles appliquees sans
                        # trace d'audit, ou proposition validee sans effet).
                        # Voir gouvernance/application_regles.py.
                        _ok, _msg, _version_id = appliquer_proposition(
                            _p["id"], st.session_state.auth, enregistrer_audit,
                        )
                        if _ok:
                            # Le cache du moteur s'invalide tout seul : le contenu
                            # du fichier de regles a change, donc son empreinte
                            # aussi (voir _construire_moteur).
                            st.success(_msg)
                            st.rerun()
                        else:
                            st.error(_msg)
                with c_rej:
                    if st.button("❌ Rejeter", key=f"rejeter_{_p['id']}", use_container_width=True):
                        _ok, _msg = rejeter_proposition(_p["id"], st.session_state.auth)
                        (st.info if _ok else st.error)(_msg)
                        st.rerun()

    with st.expander("Historique des propositions traitees"):
        _hist = lister_historique_propositions()
        if _hist:
            st.dataframe(pd.DataFrame(_hist), use_container_width=True)
        else:
            st.caption("Aucune proposition traitee pour le moment.")

    # ----------------------------------------------------------------- #
    # Versions du fichier de regles
    # ----------------------------------------------------------------- #
    section("Historique des versions")
    st.caption(
        "Chaque changement applique cree une nouvelle version horodatee. Rien n'est jamais "
        "ecrase : revenir a une version anterieure passe par une nouvelle proposition, "
        "confirmee comme n'importe quel autre changement (double validation)."
    )
    _versions = lister_versions(limite=50)
    if not _versions:
        st.caption("Aucune version enregistree pour le moment.")
    else:
        for _v in _versions:
            with st.container(border=True):
                c_info, c_action = st.columns([4, 1])
                with c_info:
                    _origine = (
                        f"proposition #{_v['proposition_id']}" if _v["proposition_id"]
                        else "version initiale"
                    )
                    st.markdown(f"**{_v['version_id']}** · {_v['horodatage']} · {_origine}")
                    st.caption(f"{_v['nom_applique_par']} — {_v['description']}")
                with c_action:
                    if st.button("↩️ Restaurer", key=f"restaurer_{_v['version_id']}", use_container_width=True):
                        _regles_version = charger_version(_v["version_id"])
                        _id_prop = proposer_changement(
                            st.session_state.auth, _regles_version,
                            f"Restauration de la version {_v['version_id']} "
                            f"({_v['horodatage']}), demandee par {st.session_state.auth['nom']}.",
                        )
                        st.success(
                            f"Proposition #{_id_prop} de restauration enregistree. Un SECOND "
                            "administrateur doit la confirmer ci-dessus pour l'appliquer."
                        )
                        st.rerun()

    st.markdown("")
    onglet_seuils, onglet_prof, onglet_json = st.tabs(["Seuils", "Professions", "JSON (lecture seule)"])

    # ----------------------------------------------------------------- #
    # Seuils : edition -> simulation d'impact -> proposition
    # ----------------------------------------------------------------- #
    with onglet_seuils:
        lignes = []
        for marche, contenu in regles["marches"].items():
            for r in contenu["regles"]:
                c = r["conditions"]
                lignes.append({
                    "marche": marche, "regle_id": r["id"],
                    "segment": r["segment"], "sous_segment": r["sous_segment"],
                    "age_min": (c.get("age") or {}).get("min"),
                    "age_max": (c.get("age") or {}).get("max"),
                    "mmm_min": (c.get("mmm") or {}).get("min"),
                    "mmm_max": (c.get("mmm") or {}).get("max"),
                    "vrd_min": (c.get("vrd") or {}).get("min"),
                    "vrd_max": (c.get("vrd") or {}).get("max"),
                })
        df_seuils = pd.DataFrame(lignes)
        edite = st.data_editor(df_seuils, use_container_width=True, num_rows="fixed",
                               disabled=["marche", "regle_id", "segment", "sous_segment"],
                               key="editeur_seuils")

        if st.button("1. Simuler l'impact de ce changement", key="btn_simuler_seuils"):
            regles_modifiees = copy.deepcopy(regles)
            index = {r["id"]: r for m in regles_modifiees["marches"].values() for r in m["regles"]}
            for _, row in edite.iterrows():
                r = index[row["regle_id"]]
                for var in ("age", "mmm", "vrd"):
                    r["conditions"].setdefault(var, {})
                    for b in ("min", "max"):
                        val = row[f"{var}_{b}"]
                        r["conditions"][var][b] = None if pd.isna(val) else float(val)
            st.session_state["_regles_candidates"] = regles_modifiees

        if "_regles_candidates" in st.session_state:
            _profils = lister_profils_audit(limite=2000)
            if not _profils and not st.session_state.historique.empty:
                _profils = st.session_state.historique.to_dict("records")
            if not _profils:
                st.info(
                    "Aucun profil disponible pour simuler l'impact (journal d'audit vide). "
                    "Effectuez d'abord quelques simulations."
                )
            else:
                _impact = simuler_impact(st.session_state["_regles_candidates"], _profils)
                _nb_changements = int(_impact["Changement"].sum()) if not _impact.empty else 0
                if _nb_changements:
                    st.warning(f"⚠️ {_nb_changements} profil(s) sur {len(_impact)} changeraient de segment avec ce changement.")
                    st.dataframe(_impact[_impact["Changement"]], use_container_width=True)
                else:
                    st.success(f"Aucun impact detecte sur les {len(_impact)} profil(s) connus.")

                _description = st.text_area(
                    "2. Justification du changement (visible par l'administrateur qui confirmera)",
                    key="description_seuils",
                )
                if st.button("3. Proposer ce changement pour validation", key="btn_proposer_seuils"):
                    _id_prop = proposer_changement(
                        st.session_state.auth, st.session_state["_regles_candidates"],
                        _description or "Modification des seuils (sans justification fournie).",
                    )
                    del st.session_state["_regles_candidates"]
                    st.success(
                        f"Proposition #{_id_prop} enregistree. Un SECOND administrateur doit la "
                        "confirmer ci-dessus pour qu'elle soit appliquee."
                    )
                    st.rerun()

    # ----------------------------------------------------------------- #
    # Professions : meme principe, sans tableau d'impact chiffre (impact
    # d'une liste de professions moins directement quantifiable qu'un seuil).
    # ----------------------------------------------------------------- #
    with onglet_prof:
        listes = regles["listes_professions"]
        nom = st.selectbox("Liste a editer", list(listes.keys()))
        df_prof = pd.DataFrame({"Profession": listes[nom]})
        edite_prof = st.data_editor(df_prof, use_container_width=True, num_rows="dynamic",
                                    key="editeur_professions")
        _description_prof = st.text_area("Justification du changement", key="description_professions")
        if st.button("Proposer ce changement de liste pour validation", key="btn_proposer_professions"):
            regles_modifiees = copy.deepcopy(regles)
            regles_modifiees["listes_professions"][nom] = [
                p for p in edite_prof["Profession"].dropna().tolist() if str(p).strip()
            ]
            _id_prop = proposer_changement(
                st.session_state.auth, regles_modifiees,
                _description_prof or f"Modification de la liste '{nom}' (sans justification fournie).",
            )
            st.success(
                f"Proposition #{_id_prop} enregistree. Un SECOND administrateur doit la "
                "confirmer ci-dessus pour qu'elle soit appliquee."
            )
            st.rerun()

    # ----------------------------------------------------------------- #
    # JSON : consultation en lecture seule uniquement. L'edition libre du
    # JSON brut a ete retiree (risque d'erreur de syntaxe ou de regle
    # incoherente sans aucun controle) : toute modification passe desormais
    # par les onglets Seuils / Professions et le workflow de proposition.
    # ----------------------------------------------------------------- #
    with onglet_json:
        st.caption(
            "Affichage en lecture seule, a titre de verification. Toute modification doit "
            "passer par les onglets 'Seuils' ou 'Professions' ci-dessus (avec simulation "
            "d'impact et double validation)."
        )
        st.text_area(
            "regles_segmentation.json", value=json.dumps(regles, ensure_ascii=False, indent=2),
            height=400, disabled=True,
        )


# --------------------------------------------------------------------------- #
# Journal d'audit
# --------------------------------------------------------------------------- #
elif page == "Journal d'audit":
    if _ROLE not in ("admin", "auditeur"):
        # Defense en profondeur : page deja retiree du menu pour ce role.
        st.error("Acces reserve aux roles Administrateur et Auditeur.")
        st.stop()
    entete_biat("Journal d'audit", "Tracabilite complete des decisions de segmentation")
    st.caption(
        "Chaque segmentation (individuelle ou en masse) est enregistree ici de facon "
        "permanente : qui, quand, quel profil, quel resultat, avec quelle version des regles. "
        "Ce journal est en ajout seul (aucune entree ne peut etre modifiee ou supprimee "
        "depuis l'application) et chainee par hash pour detecter toute alteration."
    )

    section("Integrite du journal")
    c_verif, c_total = st.columns([2, 1])
    with c_verif:
        if st.button("🔍 Verifier l'integrite du journal"):
            ok, message = verifier_integrite_audit()
            if ok:
                st.success(message)
            else:
                st.error(message)
    with c_total:
        kpi("Entrees enregistrees", compter_audit(), icone="🛡️")

    section("Historique des decisions")
    entrees = lister_audit(limite=500)
    if not entrees:
        st.info("Aucune decision enregistree pour le moment.")
    else:
        df_journal = pd.DataFrame(entrees)
        c1, c2 = st.columns(2)
        with c1:
            filtre_type = st.multiselect(
                "Type d'action", sorted(df_journal["type_action"].unique()),
                default=sorted(df_journal["type_action"].unique()),
            )
        with c2:
            filtre_utilisateur = st.multiselect(
                "Utilisateur", sorted(df_journal["identifiant_utilisateur"].unique()),
                default=sorted(df_journal["identifiant_utilisateur"].unique()),
            )
        df_affiche = df_journal[
            df_journal["type_action"].isin(filtre_type)
            & df_journal["identifiant_utilisateur"].isin(filtre_utilisateur)
        ]
        st.caption(f"{len(df_affiche)} entree(s) affichee(s) sur les {len(df_journal)} les plus recentes.")
        st.dataframe(df_affiche, use_container_width=True)
        st.download_button(
            "Exporter le journal affiche (CSV)",
            data=df_affiche.to_csv(index=False).encode("utf-8"),
            file_name="journal_audit.csv", mime="text/csv",
        )
