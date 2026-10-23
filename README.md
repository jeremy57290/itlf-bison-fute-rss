# ITLF V3.9.2 – Flux IFTTT de test séparé

Cette version conserve **rss.xml inchangé** et crée en parallèle **rss-ifttt.xml** avec les mêmes événements, mêmes dates et mêmes liens Google Maps, mais des GUID sous forme d'URL HTTPS uniques et stables (`https://www.google.com/maps?q=...#itlf-<hash>`). Le but est de tester l'hypothèse d'une incompatibilité IFTTT avec les GUID `urn:itlf:...` sans toucher au flux principal.

## Installation

1. Remplacer `itlf_rss.py` par celui fourni.
2. Dans `.github/workflows/rss.yml`, ajouter `rss-ifttt.xml` à la commande `git add` qui publie les fichiers générés. Vérifier que le workflow pousse effectivement le fichier dans la branche utilisée par GitHub Pages.
3. Exécuter le workflow GitHub Actions et vérifier l'URL : `https://jeremy57290.github.io/itlf-bison-fute-rss/rss-ifttt.xml`.
4. Créer une **nouvelle** applet IFTTT avec cette URL, sans changer l'applet ou le flux principal.

Si IFTTT refuse toujours ce flux, le problème n'est pas uniquement le format des GUID. Le test ne garantit pas la compatibilité d'IFTTT. La création d'une nouvelle applet peut déclencher des alertes existantes selon le comportement d'IFTTT.
