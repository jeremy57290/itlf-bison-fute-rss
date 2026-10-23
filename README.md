# ITLF RSS V3.9 — Diagnostic accidents et obstacles

Basée sur la V3.8. Aucun changement de la logique de publication, des catégories, des GUID ou du filtrage territorial.

## Nouveauté

À chaque exécution réussie, création de `diagnostic_incidents.json` :
- `counts.accident` et `counts.obstacle` : total dans la source, actifs en Lorraine, inactifs, hors Lorraine/non localisables ;
- `records` : jusqu'à 100 exemples par catégorie, avec type DATEX, éventuels sous-types, détails, validité et localisation.

Les statistiques comptent **tous** les enregistrements de ces deux catégories ; seules les listes d'exemples sont limitées. Les événements non reconnus ne sont pas classés comme accidents par supposition.

## Installation

Remplacer `itlf_rss.py` dans le dépôt. Conserver les autres fichiers. Dans `.github/workflows/rss.yml`, ajouter `diagnostic_incidents.json` à l'étape `git add` / commit afin de récupérer le diagnostic depuis GitHub. Relancer le workflow et transmettre le JSON.

## Précautions

Le diagnostic n'améliore pas encore les titres des obstacles et ne garantit pas que tous les accidents routiers soient remontés par la source Bison Futé. Les fichiers RSS et GeoJSON restent générés selon les règles V3.8.
