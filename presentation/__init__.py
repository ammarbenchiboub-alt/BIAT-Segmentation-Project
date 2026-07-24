"""
Smart Response Renderer — moteur de rendu intelligent des reponses du chatbot.

Couche de PRESENTATION strictement separee de la logique metier :
  - `plan`  : planificateur pur (reponse -> blocs abstraits), testable sans UI ;
  - `rendu` : adaptateur Streamlit (blocs -> composants), reutilise le theme.

Le chatbot (`chatbot.expert`) et le moteur (`core.engine`) restent inchanges :
ce paquet ne fait que choisir la meilleure mise en forme d'une reponse deja
calculee.

Usage typique dans l'application :
    from presentation import afficher_reponse
    afficher_reponse(chatbot.repondre(question))
"""
from .fiche import generer_fiche_html
from .plan import planifier_reponse
from .rendu import afficher_reponse, injecter_css_rendu

__all__ = [
    "planifier_reponse", "afficher_reponse", "injecter_css_rendu",
    "generer_fiche_html",
]
