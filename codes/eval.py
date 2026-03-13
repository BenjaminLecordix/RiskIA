import os
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.utils import get_action_masks
from risk_game.gym_env import RiskGymEnv

def evaluate_model(model_path, num_games=100):
    #print(f"Chargement du modèle : {model_path}...")
    env = RiskGymEnv()
    
    if not os.path.exists(model_path + ".zip"):
        #print("Erreur : Modèle introuvable.")
        return

    model = MaskablePPO.load(model_path)
    
    wins = 0
    losses = 0
    total_turns = 0

    #print(f"Lancement de {num_games} parties d'évaluation...\n")

    for i in range(num_games):
        obs, info = env.reset()
        done = False
        
        while not done:
            # On récupère le masque des actions valides
            action_masks = get_action_masks(env)
            
            # L'IA choisit l'action de manière déterministe (meilleure action connue)
            action, _states = model.predict(obs, action_masks=action_masks, deterministic=True)
            
            obs, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated

        # Fin de partie : Qui a gagné ?
        # Dans RiskGymEnv, le bot est le joueur 1, l'IA est le joueur 0
        ia_alive = env.engine.players[0].is_alive
        
        if ia_alive:
            wins += 1
        else:
            losses += 1
            
        total_turns += env.engine.turn_count if hasattr(env.engine, 'turn_count') else 0
        
        # Petit affichage de progression
        if (i + 1) % 10 == 0:
            print(f"Parties jouées : {i + 1}/{num_games} | Victoires IA : {wins}")

    #print("\n" + "="*30)
    #print("RÉSULTATS DE L'ÉVALUATION")
    #print("="*30)
    #print(f"Victoires IA : {wins} ({wins/num_games * 100:.1f}%)")
    #print(f"Victoires Bot : {losses} ({losses/num_games * 100:.1f}%)")
    #print("="*30)

if __name__ == "__main__":
    # Assure-toi que le chemin correspond au nom de ta dernière sauvegarde
    evaluate_model("risk_game/models/PPO/risk_v10_ckpt_74008321_steps", num_games=100)