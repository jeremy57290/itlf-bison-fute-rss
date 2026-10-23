# ITLF V3.5 — audit des catégories DATEX II

Cette version reprend le script V3.4 transmis le 23 octobre 2026.

**Aucune catégorie supplémentaire n'est publiée.** Le filtrage géographique, les règles de validité, les titres, les descriptions et la conservation temporaire restent inchangés.

Le fichier `rejets.json` reçoit quatre nouveaux champs :
- `unknown_types_in_lorraine` : types DATEX II non reconnus, actifs et géolocalisés dans les départements 54, 55, 57, 88 ;
- `unknown_types_in_lorraine_examples` : jusqu'à cinq exemples par type, pour évaluer les nouvelles catégories pertinentes ;
- `unknown_types_inactive` : types non reconnus et inactifs ;
- `unknown_types_location_rejections` : types non reconnus mais rejetés par la géolocalisation.

Les totaux `accepted` et `rejected_by_reason` restent calculés selon les règles V3.4.

## Installation
Remplacer uniquement `itlf_rss.py` à la racine du dépôt GitHub et relancer le workflow existant. Ne pas supprimer `state.json` ni `lorraine_departements.geojson`. Après exécution, partager `rejets.json` pour analyser les catégories avant toute activation.
