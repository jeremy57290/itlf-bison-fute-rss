# ITLF – RSS DATEX II

## Installation
Python 3.10+ sans dépendance. Exécuter `python itlf_rss.py`.
Le script télécharge un instantané DATEX II SituationPublication et écrit `rss.xml` et `state.json`.
Configurer la source via `ITLF_DATEX_URL` si nécessaire.

## Publication
Déposer les fichiers dans un dépôt GitHub, activer GitHub Actions, puis GitHub Pages pour exposer `rss.xml` (ou héberger ce fichier sur son propre serveur). Le workflow tente une mise à jour toutes les 5 minutes; GitHub Actions peut retarder ou ignorer des exécutions planifiées. Pour une cadence stricte, utiliser un cron sur VPS.

## Précautions
- **Prototype à valider sur un XML événementiel réel** : le fichier Myrabel fourni précédemment est un `MeasuredDataPublication`, pas une `SituationPublication`.
- Le filtre géographique est volontairement conservateur : code département explicite ou coordonnées dans une boîte englobante approximative. Des événements sans ces informations ne seront pas publiés; les coordonnées dans la boîte peuvent inclure des zones limitrophes hors Lorraine. Pour une production fiable, utiliser les limites géographiques exactes des départements.
- La catégorisation est heuristique : vérifier les variantes DATEX II réelles et les restrictions de voie avant diffusion publique.
- Les routes étrangères (Luxembourg, Belgique, Allemagne) nécessitent des sources distinctes. Ici seuls les secteurs français sont couverts.
- Deux absences successives font disparaître un événement du RSS, sans publier d'avis de fin. Une source qui fournit des événements différentiels au lieu d'instantanés complets ne doit pas être utilisée telle quelle.
- Si le téléchargement ou l'analyse échoue, le flux précédent est conservé.
- Les descriptions restent génériques si les champs géographiques sont incomplets.
- Attribution : données Bison Futé / DIR, Licence Ouverte 2.0.
