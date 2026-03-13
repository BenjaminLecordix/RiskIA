# Risk RL (Maskable PPO)

Ce dépôt contient un agent RL entraîné pour jouer à Risk (1v1) avec un environnement Gymnasium et action masking.
L’objectif est d’obtenir un agent stable, performant et reproductible, avec un pipeline d’entraînement et d’évaluation clair.

## Fonctionnalités
- Environnement 1v1 avec phases Risk (reinforce / attack / fortify)
- Action masking via `sb3_contrib` (MaskablePPO)
- Adversaires scriptés (naive, aggressive, random) + self-play
- Curriculum d’adversaires (phases A/B/C)
- Checkpoints, best model, crash-save et early-stop

## Structure du projet
- `codes/` : scripts CLI (train, eval, play)
- `codes/risk_game/` : environnement, moteur, bots, constantes
- `codes/risk_game/models/` : checkpoints (non versionnés)
- `codes/risk_game/logs/` : logs TensorBoard (non versionnés)
- `codes/risk_game/eval_reports/` : rapports d’éval (non versionnés)

## Règles de Risk (résumé)
Ce projet implémente un Risk 1v1 avec des simplifications adaptées au RL, tout en conservant les principes clés.

**Mise en place**
- La carte est divisée en 42 territoires regroupés par continents.
- Chaque territoire appartient à un joueur et contient un nombre d’armées.
- Les territoires sont distribués puis des armées initiales sont placées automatiquement.

**Objectif**
- Éliminer l’adversaire en contrôlant tous les territoires.

**Phases d’un tour**
1. Reinforce (renforts)
2. Attack (attaques)
3. Fortify (fortification)

**Renforts**
- Renforts de base = `max(3, territoires / 3)`.
- Bonus de continent si contrôle total (valeurs définies dans `codes/risk_game/consts.py`).

**Attaque**
- Attaques possibles uniquement depuis un territoire adjacent.
- L’attaquant doit garder au moins 1 armée sur le territoire source.
- Résolution par dés (jusqu’à 3 dés pour l’attaquant, 2 pour le défenseur).
- En cas de défaite, le territoire reste au défenseur.
- En cas de victoire, le territoire change de propriétaire.

**Fortification**
- Déplacement d’armées entre deux territoires connectés contrôlés par le même joueur.
- Le joueur doit laisser au moins 1 armée sur le territoire source.

**Cartes**
- Si un joueur conquiert au moins un territoire dans le tour, il gagne une carte.
- Les cartes peuvent être échangées contre des renforts (combinaisons standard).

**Fin de partie**
- La partie se termine lorsqu’un seul joueur possède des territoires.

## Installation
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Entraînement
```bash
python3 codes/train.py
```
Le script sauvegarde les checkpoints dans `codes/risk_game/models/PPO/` et met à jour `risk_v11_best.zip`.

### Paramètres utiles
Le cœur des réglages se trouve dans `codes/train.py` :
- `timesteps` : budget total d’entraînement.
- `OpponentCurriculumCallback` : change le mix d’adversaires selon la phase.
- `SelfPlaySnapshotCallback` : snapshot périodique pour le self-play.

## Évaluation
```bash
python3 codes/eval.py
```
Par défaut l’éval lance 100 parties. Modifie le modèle évalué dans `codes/eval.py`.

## Démo (watch)
```bash
python3 codes/play.py
```
Charge un modèle et joue une partie en mode démonstration.

## Notes importantes
- Les fichiers volumineux (checkpoints, logs, rapports) sont ignorés par Git via `.gitignore`.
- Le self-play utilise un snapshot périodique (`risk_v11_selfplay_latest`).

## Modèles
Les modèles sont stockés localement dans `codes/risk_game/models/PPO/`.
Le meilleur modèle courant est référencé par `risk_v11_best.zip`.

## Licence
À définir.
