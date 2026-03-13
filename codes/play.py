from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from risk_game.gym_env import RiskGymEnv
import time

def mask_fn(env):
    return env.action_masks()

def watch_game(model_name):
    # 1. Charger l'environnement
    env = RiskGymEnv()
    env = ActionMasker(env, mask_fn)

    # 2. Charger le modèle entraîné
    model_path = "risk_game/models/PPO/" + model_name
    #print(f"Chargement du modèle depuis {model_path}...")
    
    try:
        model = MaskablePPO.load(model_path)
    except FileNotFoundError:
        #print("Erreur : Le modèle n'existe pas. Lance train.py d'abord !")
        return

    # 3. Lancer une partie
    obs, _ = env.reset()
    done = False
    turn = 0
    
    #print("\n=== DÉBUT DU MATCH DE DÉMONSTRATION ===")
    
    while not done:
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
        time.sleep(0) 

    #print("\n=== PARTIE TERMINÉE ===")
    winner = "IA (Agent 0)" if reward > 0 else "NaiveBot (Agent 1)"
    #print(f"Vainqueur : {winner}")

if __name__ == "__main__":
    watch_game("risk_v10_ckpt_74008321_steps") 