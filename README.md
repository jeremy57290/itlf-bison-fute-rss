# ITLF France – V3.2

Cette version ne modifie pas le flux Luxembourg.

## Fichiers
- `itlf_rss.py` : générateur RSS, GeoJSON et diagnostic.
- `prepare_boundaries.py` : récupère une fois les polygones des départements 54, 55, 57, 88.
- `lorraine_departements.geojson` : créé par le script précédent, **non inclus** dans l'archive.
- `rss.xml`, `state.json`, `traffic.geojson`, `rejets.json` : sorties du générateur.

## Installation GitHub
1. Ajoutez/remplacez `itlf_rss.py` et ajoutez `prepare_boundaries.py` à la racine.
2. Dans `.github/workflows/rss.yml`, avant `python itlf_rss.py`, ajoutez :

       if [ ! -f lorraine_departements.geojson ]; then python prepare_boundaries.py; fi

3. Dans l'étape de commit, utilisez :

       git add rss.xml state.json traffic.geojson rejets.json lorraine_departements.geojson

4. Enregistrez puis exécutez le workflow. La première exécution récupère
   les limites via france-geojson (GitHub). Les suivantes utilisent la copie
   conservée dans le dépôt, sans téléchargement supplémentaire.

## Sécurité / limites
- Si le fichier de limites manque et que le téléchargement échoue, le programme
  refuse de remplacer le RSS par un flux approximatif.
- Seuls les événements ayant un point GPS situé dans un des quatre polygones
  sont retenus. Les événements sans coordonnées et les tronçons traversant
  la frontière départementale peuvent être rejetés même s'ils sont pertinents.
- Les données france-geojson proviennent d'un projet tiers et doivent être
  vérifiées avant usage de production. Source :
  https://github.com/gregoiredavid/france-geojson
- Les compteurs `rejets.json` distinguent désormais :
  `missing_coordinates`, `outside_department`, `conflicting_location`,
  ainsi que les catégories et statuts les plus souvent exclus.
- Les dates de récurrence DATEX II et certaines classifications restent à
  auditer sur le XML réel. Ne pas automatiser les publications sociales sans
  validation du flux et de son périmètre.
- Les tests effectués sont synthétiques, pas un test en ligne de Bison Futé.
