# ITLF RSS V3.4

## Changements
- Priorité à la localité explicitement fournie dans les descriptions DATEX plutôt qu'aux communes utilisées comme repères kilométriques.
- Reformulation légère des repères « début/fin », sans supprimer les distances ni les directions fournies.
- Maintien du filtrage strict par polygones des départements 54, 55, 57, 88.
- Conservation des GUID, des dates d'origine, de `state.json` et du workflow GitHub Actions.

## Installation
Remplacer uniquement `itlf_rss.py` à la racine du dépôt GitHub puis lancer le workflow. Ne pas supprimer `state.json` ni `lorraine_departements.geojson`.

## Limites
La localisation est issue des champs DATEX et peut rester un repère approximatif. La direction n'est pas recalculée et aucun sens 1/2 n'est publié.
