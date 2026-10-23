# ITLF RSS V3.3

Mise à jour de présentation basée sur la V3.2 validée.

## Installation

1. Remplacer uniquement `itlf_rss.py` à la racine du dépôt GitHub.
2. Conserver `prepare_boundaries.py`, `lorraine_departements.geojson` et `.github/workflows/rss.yml` existants.
3. Ne pas supprimer `state.json` : les entrées encore actives seront renouvelées avec les nouveaux titres et descriptions.
4. Commit, puis GitHub Actions > Actualisation RSS ITLF > Run workflow.
5. Vérifier `rss.xml`, `traffic.geojson`, `rejets.json`.

## Changements

- Titre : type – axe – localité (département), si la source renseigne ces éléments.
- Localité de repli tirée d'une description DATEX explicite de type `situé 423 m à l'ouest de Nancy Laxou`.
- Suppression de la répétition `Département 54` dans la description quand le titre indique déjà `(54)`.
- Destination raccourcie uniquement pour les préfixes `Allemagne -` et `Suisse -`, sans déduire de direction à partir des sens DATEX.
- Aucun changement au filtrage polygonal, à la publication, ni aux règles de validité.

## Prudence

Les localités sont celles indiquées dans la source et non une géolocalisation inverse. Les titres peuvent être approximatifs lorsque la source décrit un repère voisin plutôt que le lieu exact. La présence d'un événement est décidée par le filtre géographique existant.
