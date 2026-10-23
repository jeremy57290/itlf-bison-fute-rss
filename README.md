# ITLF RSS – version 3 (prototype prudent)

Ce générateur produit `rss.xml`, `traffic.geojson` et `state.json` à partir d'un instantané DATEX II SituationPublication. Python 3.10+ ; aucune dépendance externe.

## Installation dans le dépôt existant

1. Remplacer `itlf_rss.py` à la racine du dépôt.
2. Dans le workflow GitHub Actions existant, s'assurer que l'étape de commit inclut **les trois fichiers** : `git add rss.xml state.json traffic.geojson`.
3. Conserver l'exécution `python itlf_rss.py` et la fréquence existante. Vérifier que `state.json` est bien persisté dans le dépôt.
4. Tester manuellement via Actions avant d'utiliser les alertes pour des publications publiques.

## Limitations importantes

- Le filtre territorial est **volontairement strict** : il n'inclut que les enregistrements comportant explicitement un code département 54, 55, 57 ou 88. Les événements sans code département, même réellement situés en Lorraine, seront écartés. La précision doit être validée sur les données DATEX II réelles. Les axes étrangers ne sont pas couverts.
- Les directions `aligned`, `opposite`, `both` ne sont jamais publiées. Seules les destinations géographiques explicitement présentes sont affichées. Une destination extraite du XML doit être vérifiée avant exploitation automatique.
- Les calendriers récurrents de validité DATEX II ne sont pas encore entièrement interprétés.
- Les coordonnées ne sont exportées que si latitude et longitude sont présentes ensemble dans un même élément parent ; certaines formes de géolocalisation DATEX II peuvent ne pas être prises en charge.
- La conservation sur une absence temporaire est de **une récupération réussie** (`MAX_MISSES=2`). Une réponse XML vide mais valide peut faire disparaître des événements après deux récupérations ; un contrôle de complétude supplémentaire est recommandé avant production.
- Les champs RSS `pubDate` conservent la date initiale pour les événements déjà connus ; les changements de contenu ne génèrent donc pas forcément de nouvelle notification chez tous les lecteurs RSS.
- Les trois fichiers sont écrits séparément et non dans une transaction globale ; une interruption entre écritures pourrait les désynchroniser.

## Validation

`python -m py_compile itlf_rss.py`

`python itlf_rss.py`

Puis inspecter les événements, les descriptions et le nombre de points géographiques. Ne pas activer de publication automatique avant vérification humaine.
