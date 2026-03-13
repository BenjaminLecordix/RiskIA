# main.py
import time
from risk_game.engine import RiskEngine
from risk_game.ai import NaiveBot

def run_game():
    game = RiskEngine(num_players=2)
    
    # Création des deux bots
    bot1 = NaiveBot(game, 0)
    bot2 = NaiveBot(game, 1)
    bots = [bot1, bot2]

    #print("=== DÉBUT DE LA PARTIE : BOT vs BOT ===")
    #print(game.get_state_summary())

    turn_count = 0
    max_turns = 100 # Sécurité pour éviter boucle infinie si blocage
    
    while turn_count < max_turns:
        current_player_id = game.current_player_index
        current_bot = bots[current_player_id]
        
        # Vérification victoire
        living_players = [p for p in game.players if p.is_alive]
        if len(living_players) == 1:
            #print(f"\n🎉 VICTOIRE DU JOUEUR {living_players[0].name} en {turn_count} tours ! 🎉")
            break

        #print(f"\n--- Tour {turn_count + 1} : {game.players[current_player_id].name} ---")
        
        # IMPORTANT : Il faut appeler start_turn pour donner les renforts
        # Mais start_turn() fait des #print et initialise la phase.
        # Dans engine.py, start_turn() appelle _next_player qui rappelle start_turn()...
        # C'est un peu récursif dans mon design précédent.
        # CORRECTION : On va appeler start_turn() manuellement ici au début, 
        # et s'assurer que l'engine ne boucle pas tout seul.
        
        # Pour faire simple avec l'architecture actuelle :
        # On assume que game.start_turn() a été appelé à l'init.
        # Le bot joue sa logique.
        # À la fin, le bot appelle engine.fortify, qui appelle _end_turn, qui appelle _next_player...
        
        # Pour garder le contrôle dans cette boucle "main", le mieux est que le bot n'appelle PAS directement
        # des fonctions qui changent le tour automatiquement, OU alors on laisse l'engine gérer le flux.
        
        # Approche choisie : On laisse le bot piloter.
        game.start_turn()
        
        current_bot.play_turn()
        
        # Attendre un peu pour lire les logs
        # time.sleep(0.5) 
        
        turn_count += 1

    if turn_count >= max_turns:
        #print("\nMatch nul (Limite de tours atteinte).")

if __name__ == "__main__":
    run_game()