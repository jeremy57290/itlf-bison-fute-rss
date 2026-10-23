# ITLF RSS V3.7

Remplacer `itlf_rss.py` dans le dépôt GitHub. Conserver `lorraine_departements.geojson`, `state.json`, `prepare_boundaries.py` et le workflow existants.

La V3.7 publie uniquement les mesures DATEX explicites `laneClosures` avec au moins une voie restreinte et `contraflow`, après validation temporelle et géographique. Les mesures d’une même situation sont regroupées en une alerte avec un GUID stable. `laneClosures` avec zéro voie restreinte et les mesures `other` restent exclues. Les anciennes catégories RSS sont conservées.

Le fichier `rejets.json` expose `management_published_records` et `management_published_situations`. Le diagnostic `mesures_a_analyser.json` reste disponible.

**Attention** : le regroupement ne fusionne que les mesures de gestion routière de la même situation, pas les travaux associés. Les coordonnées de l’alerte regroupée correspondent au premier enregistrement; elles ne représentent pas nécessairement toute l’étendue de la mesure. Les catégories historiques et GUID existants sont conservés.
