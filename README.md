# CalcIFC2

Application web pour importer un fichier IFC, sélectionner une zone normative et obtenir un pré-rapport d'analyse (charges, résumé de structure, historique).

## Démarrage rapide

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Puis ouvrez <http://localhost:5000>.

## Fonctionnalités

- Import IFC Tekla (ou autre) avec stockage des versions.
- Pré-calcul des charges neige/vent/sismique selon la zone et l'usage du bâtiment.
- Comptage des éléments structurels (poutres, poteaux, contreventements, platines, fixations).
- Historique des analyses avec téléchargement d'un pré-rapport JSON.

## Limites actuelles

- Le parsing IFC est basé sur des expressions régulières (non complet).
- Le moteur Eurocode détaillé reste à intégrer.
- Les règles de dimensionnement doivent être enrichies pour couvrir tous les cas.
