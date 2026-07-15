# Note BIAT 2023-06 - Nouvelle segmentation de la clientele PBD (reference metier)

> Source unique de reference. Document du 14/02/2023 (Ref. Note au reseau 2020-02).
> Seuils en DT (1 mD = 1000 DT). Combinaison MMM/VRD : OU (OR).
> Marches geres par l'application : PART, PRO, TRE, ENR (TPME exclu).

## Variables de segmentation
- Valeur actuelle du client : CA declare/rapproche par le MMM ; Mouvements Mensuels Moyens (MMM) ; Total des avoirs stables (VRD) incluant depots a vue, epargne, a terme, produits d'assurance et financiers.
- Donnees sociodemographiques (fiche client T24) : Age (limite jeunes portee a 30 ans), Categorie client, Profession (PL et professions a potentiel), Nationalite, Qualite de residence.
- Revenus mensuels nets declaratifs : utilises pour la pre-segmentation de conquete uniquement (hors simulation individuelle de cette application).

## Marche PART (Particuliers)
### Haut de Gamme
- Fortunes : quel que soit l'age, VRD >= 500 mD.
- Patrimoniaux : > 30 ans, MMM >= 10 mD OU VRD entre 300 et 500 mD.
- Affluent : > 30 ans, MMM >= 4 mD OU VRD entre 100 et 300 mD. Les professions a potentiel (annexe 4) sont integrees a l'Affluent independamment du MMM (exceptions CSP / secteur public : medecins des hopitaux, magistrats, profs universitaires...).
- Affluent / epargnants et deposants exclusifs : VRD entre 100 et 300 mD (comptes epargne / depots a terme uniquement).
### Classe Moyenne
- Les salaries : > 30 ans, secteur public, MMM entre 1 et 4 mD OU VRD entre 5 et 100 mD.
- Epargnants et deposants exclusifs : > 30 ans, VRD entre 5 et 100 mD.
### Grand Public
- Particuliers : MMM < 1 mD OU VRD < 5 mD.
- Epargnants et deposants exclusifs : VRD < 5 mD.
- Clients dormants : MMM < 100 D OU VRD < 100 D, et Nbr operations = 0 sur 12 mois.
### Les Jeunes
- Enfants et Eleves : <= 18 ans, MMM < 10 mD, VRD < 300 mD.
- Etudiants : quel que soit l'age, profession = Etudiant, MMM < 10 mD, VRD < 300 mD.
- JDA a potentiel : > 18 et <= 30 ans, professions a potentiel (annexe 4).
- Autres JDA : > 18 et <= 30 ans, autres professions.

## Marche PRO (Professionnels)
### Haut de Gamme
- Fortunes : quel que soit l'age, VRD >= 500 mD.
- Professions Liberales : profession liberale declaree (annexe 5), quel que soit l'age et le montant.
- Professionnels : MMM >= 100 mD OU VRD >= 200 mD (professions a potentiel hors PL, annexe 4).
### Classe Moyenne
- Commercants & Artisans : MMM entre 5 et 100 mD OU VRD entre 15 et 200 mD.
### Grand Public
- Commercants & Artisans : MMM < 5 mD OU VRD < 15 mD.
- Clients dormants : MMM < 500 D OU VRD < 500 D, Nbr operations = 0.

## Marche TRE (Tunisiens Residents a l'Etranger)
- Premium : profession a potentiel (annexe 4) OU MMM >= 10 mD OU VRD >= 50 mD.
- Potentiel moyen : MMM >= 5 mD OU VRD entre 25 et 50 mD.
- Faible potentiel : MMM < 5 mD, VRD < 25 mD.
- TRE Inactif : comptes non mouvementes pendant une annee.
- Residence : le TRE doit respecter la reglementation de change (centre d'interet a l'etranger, titre de sejour valide). Statut maintenu 2 ans max apres retour definitif.

## Marche ENR (Etrangers Non Residents)
> Le tableau de la note indique explicitement "MMM ou Total des avoirs".
- Premium : MMM >= 10 mD OU VRD >= 60 mD.
- Potentiel moyen : MMM >= 5 mD OU VRD entre 30 et 60 mD.
- Faible potentiel : MMM < 5 mD, VRD < 30 mD.
- Inactifs : comptes non mouvementes pendant une annee.
- Residence : l'ENR ne detient pas de titre de sejour en Tunisie ; sejour <= 3 mois successifs. Piece : passeport etranger valide.

## Annexe 4 - Professions a potentiel
- Professionnels HG : Medecins generalistes, dentistes, veterinaires, specialistes ; Pharmaciens ; Biologistes et assimiles ; Opticiens-lunetiers ; Avocats ; Experts-comptables ; Ingenieurs ; Architectes et urbanistes.
- Salaries (Affluents / TRE Premium / JDA Potentiel) : Medecins generalistes, dentistes, veterinaires, Medecins (fonction publique, si resident) ; Pharmaciens ; Biologistes et assimiles ; Magistrats ; Ingenieurs ; Experts-comptables ; Architectes et urbanistes ; Enseignants universitaires ; Chefs de mission diplomatique et assimiles ; Hauts fonctionnaires (si resident) ; Pilotes et officiers de pont.

## Annexe 5 - Professions liberales
- PL strategiques : Medecins specialistes, generalistes, dentistes, veterinaires ; Pharmaciens ; Biologistes et assimiles ; Experts-comptables.
- Autres PL : Architectes et urbanistes ; Ingenieurs ; Medecins de la fonction publique et assimiles ; Opticiens-lunetiers ; Professions paramedicales ; Avocats ; Huissiers de justice, notaires, experts judiciaires et assimiles ; Conseillers et consultants ; Transitaires et commissionnaires.
