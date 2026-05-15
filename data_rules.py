RULES_BIAT_2023 = {
    "Identification": {
        "PART": "Via Code Profession",
        "PRO": "Via Code Activité (Ex: 58=Commerçant, 56=Artisan, 54=Industriel)"
    },
    "Segments": {
        "Haut_de_Gamme": {
            "Fortunés": "Avoirs (VRD) >= 500 mD",
            "Patrimoniaux": "100 mD <= VRD < 500 mD",
            "Affluent": {
                "Age": "> 30 ans",
                "Financier": "MMM >= 100 mD OU VRD >= 100 mD",
                "Potentiel": "Professions à fort potentiel (Ingénieurs, Cadres, Pilotes) classées ici même si MMM est inférieur"
            },
            "Professions_Liberales_HG": [
                "Médecins", "Pharmaciens", "Dentistes", 
                "Avocats", "Notaires", "Huissiers",
                "Architectes", "Experts Comptables", "Géomètres"
            ]
        },
        "Les_Jeunes": {
            "Enfants": "Age <= 16 ans",
            "Etudiants": "Entre 16 et 25 ans",
            "JDA_Potentiel": "Age <= 30 ans + Profession à potentiel",
            "Autres_JDA": "Age <= 30 ans (Professions standards)"
        }
    },
    "Seuils_Comparatifs_10": {
        "Particuliers": {
            "MMM": "Passage de 50 mD à 100 mD",
            "VRD": "Passage de 20 mD à 100 mD"
        },
        "Professionnels": {
            "MMM": "Passage de 2.5 mD à 4 mD",
            "VRD": "Passage de 150 mD à 200 mD"
        },
        "Age_Affluent": "Passage de 22 ans à 30 ans"
    },
    "PME_Exclues": [
        "ASSET KINGS", "PME Internationales", "PME Locales", 
        "Nouvelles PME", "PME Transactionnelles"
    ]
}