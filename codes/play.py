import os
import time

from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from risk_game.gym_env import RiskGymEnv

def mask_fn(env):
    return env.action_masks()

def watch_game(model_name, visualize=True, event_delay=0.5):
    # 1. Charger l'environnement
    base_env = RiskGymEnv()
    env = ActionMasker(base_env, mask_fn)

    # 2. Charger le modèle entraîné
    base_dir = os.path.dirname(__file__)
    model_path = os.path.join(base_dir, "risk_game", "models", "PPO", model_name)
    #print(f"Chargement du modèle depuis {model_path}...")
    
    try:
        model = MaskablePPO.load(model_path)
    except FileNotFoundError:
        print(f"Erreur : modèle introuvable: {model_path}")
        return

    visualizer = None
    if visualize:
        from risk_game.visualizer import RiskVisualizer

        visualizer = RiskVisualizer(
            base_env.engine,
            update_on_event=True,
            event_delay=event_delay,
        )

    # 3. Lancer une partie
    obs, _ = env.reset()
    if visualizer:
        visualizer.render()
    done = False
    turn = 0
    
    #print("\n=== DÉBUT DU MATCH DE DÉMONSTRATION ===")
    
    while not done:
        if visualizer and visualizer.is_closed():
            break
        # L'IA prédit la meilleure action en tenant compte des masques
        # action_masks=env.env.action_masks() est nécessaire pour la prédiction
        action_masks = env.action_masks()
        action, _states = model.predict(obs, action_masks=action_masks, deterministic=True)
        
        # Exécution dans le jeu
        obs, reward, terminated, truncated, info = env.step(action)
        
        # Affichage un peu plus humain
        # On peut accéder à l'engine interne via env.env (car env est un wrapper)
        real_env = env.env 
        
        # On affiche juste un résumé périodique pour ne pas spammer
        # ou on laisse les #prints de l'engine s'afficher
        
        done = terminated or truncated
        turn += 1
        
        # Ralentir pour pouvoir lire ce qui se passe
        if visualizer:
            if not visualizer.render():
                break
        time.sleep(0)

    #print("\n=== PARTIE TERMINÉE ===")
    winner = "IA (Agent 0)" if reward > 0 else "NaiveBot (Agent 1)"
    #print(f"Vainqueur : {winner}")

if __name__ == "__main__":
    watch_game("risk_v11_best") 
