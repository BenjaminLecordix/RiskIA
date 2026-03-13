# Risk RL (Maskable PPO)

Agent RL entraîné pour jouer à Risk (1v1) avec un environnement Gymnasium et action masking.

## Points clés
- Environnement 1v1 avec phases Risk (reinforce/attack/fortify)
- Action masking via `sb3_contrib` (MaskablePPO)
- Adversaires scriptés + self-play
- Curriculum d’adversaires (phases A/B/C)

## Structure du projet
- `codes/` : scripts d’entraînement/évaluation/démo
- `codes/risk_game/` : environnement, moteur, IA bots, constantes
- `codes/risk_game/models/` : checkpoints (non versionnés)
- `codes/risk_game/logs/` : logs TensorBoard (non versionnés)
- `codes/risk_game/eval_reports/` : rapports d’éval (non versionnés)

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

## Évaluation
```bash
python3 codes/eval.py
```
Par défaut, l’éval lance 100 parties. Tu peux modifier le modèle évalué dans `codes/eval.py`.

## Démo (watch)
```bash
python3 codes/play.py
```
Le script charge un modèle et joue une partie en mode démonstration.

## Notes importantes
- Les fichiers volumineux (checkpoints, logs, rapports) sont ignorés par Git via `.gitignore`.
- Si tu veux publier des modèles, utilise plutôt Git LFS ou des releases GitHub.
- Le self-play utilise un snapshot périodique (`risk_v11_selfplay_latest`).

## Modèles et checkpoints
Les modèles sont stockés localement dans `codes/risk_game/models/PPO/`.
Le meilleur modèle courant est référencé par `risk_v11_best.zip`.

## Licence
À définir si tu veux ouvrir le dépôt.
