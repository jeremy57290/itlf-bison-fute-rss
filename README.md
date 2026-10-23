# ITLF RSS V3.9.1 — Compatibilité IFTTT

Correctif minimal basé sur V3.9 : chaque `<item>` RSS comporte désormais un `<link>` HTTPS valide pointant vers Google Maps à l'emplacement de l'événement. En absence de coordonnées, le lien pointe vers le site général de Bison Futé.

Le `<guid>` et les règles de filtrage restent inchangés. Aucun autre fichier n'a besoin d'être modifié. Remplacer `itlf_rss.py` dans le dépôt GitHub puis relancer le workflow.

Attention : le lien Google Maps indique la position de l'événement, pas une page de détail ou un suivi de l'événement en temps réel.
