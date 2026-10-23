# ITLF RSS V3.6 — Diagnostic des mesures DATEX II

Remplacer uniquement `itlf_rss.py` dans le dépôt GitHub, puis exécuter le workflow habituel.

Nouveau fichier généré : `mesures_a_analyser.json`. Il contient les champs DATEX II des enregistrements de catégories inconnues, actifs et situés dans les départements 54, 55, 57 et 88. Aucun de ces enregistrements n’est publié dans le RSS.

Le flux RSS, les GUID, le GeoJSON, le filtrage géographique et les règles d’expiration restent inchangés.

**Attention :** si le workflow ne commit pas `mesures_a_analyser.json`, ajouter ce fichier à l'étape `git add` du workflow (`git add rss.xml traffic.geojson state.json rejets.json mesures_a_analyser.json`), puis relancer. Ne pas supprimer `state.json`.

Transmettre ensuite `mesures_a_analyser.json` pour examiner les valeurs réelles des mesures et leurs attributs.
