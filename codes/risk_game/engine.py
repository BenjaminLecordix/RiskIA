# risk/engine.py
import random
from collections import Counter
from .consts import (
    TERRITORIES_DATA, STARTING_ARMIES, CONTINENT_BONUSES,
    CARD_TYPES, TRADE_REWARDS, CARD_INFANTRY, CARD_CAVALRY, CARD_ARTILLERY, MAX_CARDS_HAND
)
from .models import Map, Player

class RiskEngine:
    def __init__(self, num_players=2):
        self.map = Map(TERRITORIES_DATA)
        self.players = self._create_players(num_players)
        self.current_player_index = 0
        self.phase = "SETUP" 
        self._listeners = []
        self._event_log = []
        self._max_event_log = 200
        self.reset()

    def _create_players(self, n):
        colors = ["Red", "Blue", "Green", "Yellow", "Black", "Gray"]
        return [Player(id=i, name=f"Agent_{i}", color=colors[i]) for i in range(n)]

    def reset(self):
        """Réinitialise le jeu pour une nouvelle partie (utile pour le RL loop)"""
        # 1. Reset map
        for t in self.map.get_all_territories():
            t.owner = None
            t.armies = 0
        
        # 2. Reset players
        start_armies = STARTING_ARMIES.get(len(self.players), 40)
        for p in self.players:
            p.armies_pool = start_armies
            p.is_alive = True
            # Episode-level state must be cleared between games.
            p.cards = []
            p.has_conquered_this_turn = False

        # 3. Distribution aléatoire des territoires (comme si on distribuait les cartes)
        territory_keys = list(self.map.territories.keys())
        random.shuffle(territory_keys)
        
        while territory_keys:
            for p in self.players:
                if not territory_keys:
                    break
                t_name = territory_keys.pop()
                territory = self.map.get_territory(t_name)
                
                # Assigner le territoire
                territory.owner = p.id
                territory.armies = 1 # 1 armée minimale obligatoire
                p.armies_pool -= 1

        # 4. Placement aléatoire du reste des armées (Setup phase rapide pour l'IA)
        # Dans un vrai jeu humain, les joueurs choisissent où mettre le reste.
        # Pour l'init IA simple, on remplit aléatoirement.
        for p in self.players:
            my_territories = self.map.get_territories_by_owner(p.id)
            while p.armies_pool > 0:
                target = random.choice(my_territories)
                target.armies += 1
                p.armies_pool -= 1

        self.phase = "REINFORCE"
        self.current_player_index = 0
        self._emit("reset")
        #print("Game Reset and Initialized.")

    def add_listener(self, listener):
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener):
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _emit(self, event_type, **payload):
        event = {"type": event_type, **payload}
        self._event_log.append(event)
        if len(self._event_log) > self._max_event_log:
            self._event_log.pop(0)
        for listener in list(self._listeners):
            try:
                listener(event)
            except Exception:
                # Ne jamais casser l'engine si un listener plante.
                pass

    def get_event_log(self):
        return list(self._event_log)

    def get_state_summary(self):
        """Helper pour visualiser l'état actuel"""
        summary = ""
        for p in self.players:
            terrs = self.map.get_territories_by_owner(p.id)
            count = len(terrs)
            total_armies = sum(t.armies for t in terrs)
            summary += f"Player {p.id}: {count} territoires, {total_armies} armées sur le plateau.\n"
        return summary

    # --- GESTION DES CARTES ---

    def draw_card(self, player_id):
        """
        Tire une carte au hasard (1/3 de chance pour chaque type) 
        et l'ajoute à la main du joueur.
        À appeler à la fin du tour si le joueur a conquis au moins un territoire.
        """
        card = random.choice(CARD_TYPES)
        player = self.players[player_id]
        player.cards.append(card)
        #print(f"Player {player_id} drew a {card} card.") # Debug
        return card

    def can_trade(self, player_id):
        """
        Vérifie si le joueur PEUT échanger (a au moins 3 cartes).
        C'est une pré-vérification simple.
        """
        return len(self.players[player_id].cards) >= 3

    def must_trade(self, player_id):
        """
        Vérifie si le joueur DOIT échanger (5 cartes ou plus).
        Règle : On ne peut pas avoir plus de 5 cartes.
        """
        return len(self.players[player_id].cards) >= MAX_CARDS_HAND

    def check_trade_value(self, cards_to_trade):
        """
        Vérifie la validité d'une combinaison de 3 cartes et retourne la récompense.
        Retourne 0 si la combinaison est invalide.
        Args:
            cards_to_trade (list): Une liste de 3 chaines de caractères (ex: ['Infantry', 'Infantry', 'Infantry'])
        """
        if len(cards_to_trade) != 3:
            return 0

        counts = Counter(cards_to_trade)
        
        # Cas 1: 3 cartes identiques
        if counts[CARD_INFANTRY] == 3:
            return TRADE_REWARDS["3_INFANTRY"]
        if counts[CARD_CAVALRY] == 3:
            return TRADE_REWARDS["3_CAVALRY"]
        if counts[CARD_ARTILLERY] == 3:
            return TRADE_REWARDS["3_ARTILLERY"]
            
        # Cas 2: 1 de chaque (3 cartes différentes)
        # Si on a 3 clés dans le Counter, c'est qu'on a 1 de chaque type
        if len(counts) == 3:
            return TRADE_REWARDS["1_EACH"]

        # Combinaison invalide (ex: 2 Infanterie + 1 Cavalier)
        return 0

    def trade_cards(self, player_id, card_indices):
        """
        Effectue l'échange de cartes.
        Args:
            player_id (int): L'ID du joueur
            card_indices (list[int]): Les index des cartes dans la main du joueur à échanger (ex: [0, 1, 4])
        Returns:
            int: Le nombre d'armées reçues (0 si échec)
        """
        player = self.players[player_id]
        
        # Vérification basique des indices
        if len(card_indices) != 3:
            #print("Erreur: Il faut sélectionner exactement 3 cartes.")
            return 0
        
        # Récupérer les cartes correspondantes
        # On trie les indices en ordre décroissant pour éviter les problèmes de décalage lors de la suppression
        sorted_indices = sorted(card_indices, reverse=True)
        
        try:
            selected_cards = [player.cards[i] for i in sorted_indices]
        except IndexError:
            #print("Erreur: Indice de carte invalide.")
            return 0

        # Vérifier la valeur
        reward = self.check_trade_value(selected_cards)
        
        if reward > 0:
            # Appliquer l'échange
            # 1. Ajouter les armées
            player.armies_pool += reward
            
            # 2. Retirer les cartes de la main (en utilisant les indices triés décroissants)
            for i in sorted_indices:
                player.cards.pop(i)
                
            self._emit(
                "trade",
                player_id=player_id,
                reward=reward,
                cards=selected_cards,
                armies_pool=player.armies_pool,
            )
            #print(f"Player {player_id} traded cards for {reward} armies.") # Debug
            return reward
        else:
            #print("Erreur: Combinaison de cartes invalide.")
            return 0
    
    # --- LOGIQUE DE RENFORT ---
    
    def _calculate_continent_bonus(self, player_id):
        """
        Calcule le bonus total lié aux continents possédés.
        """
        bonus = 0
        for continent_name, territories in self.map.continents.items():
            # Vérifie si TOUS les territoires du continent appartiennent au joueur
            if all(t.owner == player_id for t in territories):
                bonus_val = CONTINENT_BONUSES[continent_name]
                bonus += bonus_val
                #print(f"Player {player_id} owns {continent_name} (+{bonus_val})") # Debug
        return bonus

    def calculate_reinforcements(self, player_id):
        """
        Calcule les armées reçues au début du tour (Territoires + Continents).
        Ne prend PAS en compte les cartes (qui sont une action séparée).
        """
        player = self.players[player_id]
        if not player.is_alive:
            return 0

        # 1. Règle des territoires : nb_territoires / 3 (arrondi inférieur)
        owned_territories = self.map.get_territories_by_owner(player_id)
        territory_bonus = len(owned_territories) // 3
        
        # Règle : Minimum 3 armées
        base_armies = max(3, territory_bonus)

        # 2. Règle des continents
        continent_bonus = self._calculate_continent_bonus(player_id)

        return base_armies + continent_bonus

    def auto_trade_cards(self, player_id):
        """
        Cherche automatiquement une combinaison de 3 cartes valide et l'échange.
        Retourne le nombre total d'armées gagnées.
        """
        player = self.players[player_id]
        total_reward = 0
        
        # On boucle tant qu'on peut échanger (car on peut avoir 6+ cartes après élimination)
        while self.can_trade(player_id):
            cards = player.cards
            counts = Counter(cards)
            indices = []

            # Priorité 1 : 3 cartes identiques
            for c_type in [CARD_INFANTRY, CARD_CAVALRY, CARD_ARTILLERY]:
                if counts[c_type] >= 3:
                    indices = [i for i, c in enumerate(cards) if c == c_type][:3]
                    break
            
            # Priorité 2 : 1 de chaque
            if not indices and len(counts) >= 3:
                # On récupère l'index d'une carte de chaque type présent
                idx_inf = next(i for i, c in enumerate(cards) if c == CARD_INFANTRY)
                idx_cav = next(i for i, c in enumerate(cards) if c == CARD_CAVALRY)
                idx_art = next(i for i, c in enumerate(cards) if c == CARD_ARTILLERY)
                indices = [idx_inf, idx_cav, idx_art]

            if indices:
                reward = self.trade_cards(player_id, indices)
                if reward > 0:
                    total_reward += reward
                else: break
            else:
                break # Aucune combinaison valide trouvée
        
        return total_reward

    def start_turn(self):
        """
        Initialise le début du tour pour le joueur courant.
        """
        player = self.players[self.current_player_index]
        
        if not player.is_alive:
            self._next_player()
            return
        
        player.has_conquered_this_turn = False

        #print(f"\n=== Début du tour : {player.name} ===")
        self.phase = "REINFORCE"
        
        # Calcul et attribution des troupes
        income = self.calculate_reinforcements(player.id)
        # Trade automatique des cartes (si possible) pour augmenter le pool d'armées
        
        player.armies_pool += income

        card_income = self.auto_trade_cards(player.id)
        
        self._emit(
            "start_turn",
            player_id=player.id,
            income=income,
            card_income=card_income,
            armies_pool=player.armies_pool,
        )
        #print(f"Renforts reçus : {income} (Total pool: {player.armies_pool})")
        
    def place_armies(self, player_id, territory_name, amount=1):
        """
        Action de placer des armées sur un territoire possédé.
        """
        if self.phase != "REINFORCE":
            #print("Erreur : Ce n'est pas la phase de renfort.")
            return False

        player = self.players[player_id]
        territory = self.map.get_territory(territory_name)

        # Vérifications
        if territory.owner != player_id:
            #print(f"Erreur : {territory_name} ne vous appartient pas.")
            return False
        
        if player.armies_pool < amount:
            #print(f"Erreur : Pas assez d'armées (Pool: {player.armies_pool}, Demandé: {amount})")
            return False

        # Application
        territory.armies += amount
        player.armies_pool -= amount
        self._emit(
            "place",
            player_id=player_id,
            territory=territory_name,
            amount=amount,
            armies=territory.armies,
            armies_pool=player.armies_pool,
        )
        #print(f"Player {player_id} placed {amount} armies on {territory_name}. (Pool left: {player.armies_pool})")
        
        # Si le pool est vide, on peut passer à la phase d'attaque (ou rester là, selon l'implémentation RL)
        return True
    
    def _next_player(self):
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        self.start_turn()
    
    # --- MÉCANIQUE D'ATTAQUE "BLITZ" ---

    def _roll_dice(self, n):
        """Lance n dés et retourne la liste triée décroissante."""
        rolls = [random.randint(1, 6) for _ in range(n)]
        rolls.sort(reverse=True)
        return rolls

    def can_attack(self, player_id, source_name, target_name):
        """Vérifie si une attaque est légale au démarrage."""
        source = self.map.get_territory(source_name)
        target = self.map.get_territory(target_name)
        
        if source.owner != player_id:
            return False, "Vous ne possédez pas le territoire source."
        if target.owner == player_id:
            return False, "Vous ne pouvez pas vous attaquer vous-même."
        if target_name not in source.neighbors:
            return False, "Les territoires ne sont pas adjacents."
        if source.armies < 2:
            return False, "Pas assez d'armées (Min 2)."
            
        return True, ""

    def attack(self, player_id, source_name, target_name):
        """
        Mode BLITZ : Attaque jusqu'à la victoire ou l'épuisement.
        Simule tous les lancers de dés nécessaires.
        
        Returns:
            bool: True si le territoire est conquis, False sinon.
        """
        # 1. Validation initiale
        valid, message = self.can_attack(player_id, source_name, target_name)
        if not valid:
            # #print(f"Attaque impossible : {message}") # Optionnel pour réduire le bruit
            return False

        source = self.map.get_territory(source_name)
        target = self.map.get_territory(target_name)
        
        old_owner_id = target.owner # On garde une trace pour vérifier l'élimination plus tard
        nb_initial_attacker = source.armies
        nb_initial_defender = target.armies

        # 2. Boucle de combat (Blitz)
        # On continue tant que l'attaquant a > 1 armée ET que le défenseur est en vie
        while source.armies > 1 and target.armies > 0:
            
            # Nombre de dés optimal pour chaque camp
            dice_att = min(3, source.armies - 1)
            dice_def = min(2, target.armies)
            
            # Lancers
            rolls_att = self._roll_dice(dice_att)
            rolls_def = self._roll_dice(dice_def)
            
            # Résolution des pertes pour ce round
            comparisons = min(dice_att, dice_def)
            for i in range(comparisons):
                if rolls_att[i] > rolls_def[i]:
                    target.armies -= 1
                else:
                    source.armies -= 1

        # 3. Résultat du Blitz
        if target.armies <= 0:
            # --- VICTOIRE ---
            #print(f"Joueur {player_id} a conquis {target.name} à {old_owner_id} depuis {source.name}! Troupes initiales : {nb_initial_attacker} attaquant, {nb_initial_defender} défenseur. Troupes finales : {source.armies} attaquant, 0 défenseur.")
            attacker_remaining = source.armies
            defender_remaining = target.armies
            success = self._handle_victory(player_id, source, target, old_owner_id)
            self._emit(
                "attack",
                player_id=player_id,
                source=source_name,
                target=target_name,
                success=True,
                attacker_losses=nb_initial_attacker - attacker_remaining,
                defender_losses=nb_initial_defender - max(defender_remaining, 0),
                attacker_remaining=attacker_remaining,
                defender_remaining=defender_remaining,
                source_armies=source.armies,
                target_armies=target.armies,
                target_owner=target.owner,
            )
            return success
        else:
            # --- DÉFAITE / ÉPUISEMENT ---
            # L'attaquant n'a plus que 1 armée, il ne peut plus continuer.
            # Le défenseur a conservé le territoire.
            #print(f"Joueur {player_id} a échoué à conquérir {target.name} à {old_owner_id} depuis {source.name}. Troupes initiales : {nb_initial_attacker} attaquant, {nb_initial_defender} défenseur. Troupes finales : {source.armies} attaquant, {target.armies} défenseur.")
            self._emit(
                "attack",
                player_id=player_id,
                source=source_name,
                target=target_name,
                success=False,
                attacker_losses=nb_initial_attacker - source.armies,
                defender_losses=nb_initial_defender - target.armies,
                attacker_remaining=source.armies,
                defender_remaining=target.armies,
                source_armies=source.armies,
                target_armies=target.armies,
                target_owner=target.owner,
            )
            return False

    def _handle_victory(self, player_id, source, target, old_owner_id):
        """Gère la conquête et le déplacement automatique de toutes les troupes."""
        # #print(f"Conquête réussie de {target.name} !")
        
        # Changement de propriétaire
        target.owner = player_id
        
        # Mouvement automatique (Simplification RL : On déplace tout le stack sauf 1)
        moving_armies = source.armies - 1
        source.armies = 1
        target.armies = moving_armies
        
        # Flag pour piocher une carte
        self.players[player_id].has_conquered_this_turn = True
        
        # Vérifier si l'ancien propriétaire est éliminé
        self._check_player_elimination(old_owner_id)
        
        return True

    def _check_player_elimination(self, player_id):
        if player_id is None: return
        
        # Si le joueur n'a plus de territoires
        if len(self.map.get_territories_by_owner(player_id)) == 0:
            eliminated_player = self.players[player_id]
            if eliminated_player.is_alive:
                #print(f"--- JOUEUR {eliminated_player.name} A ÉTÉ ÉLIMINÉ ! ---")
                eliminated_player.is_alive = False
                self._emit("elimination", player_id=player_id)
                # Note: Dans le Risk complet, on récupère les cartes ici.
                # Pour l'instant on laisse simple.

    # --- PHASE DE FORTIFICATION ---

    def _check_path(self, player_id, start_node, end_node):
        """
        Vérifie s'il existe un chemin continu de territoires appartenant au player_id
        entre start_node et end_node via un algorithme BFS (Breadth-First Search).
        """
        if start_node == end_node:
            return True

        # File d'attente pour le BFS
        queue = [start_node]
        # Ensemble des territoires visités pour éviter les boucles
        visited = {start_node.name}

        while queue:
            current = queue.pop(0)
            
            # Si on atteint la cible
            if current == end_node:
                return True

            # Explorer les voisins
            for neighbor_name in current.neighbors:
                if neighbor_name not in visited:
                    neighbor_obj = self.map.get_territory(neighbor_name)
                    
                    # Condition critique : Le voisin doit appartenir au même joueur
                    if neighbor_obj.owner == player_id:
                        visited.add(neighbor_name)
                        queue.append(neighbor_obj)
        
        return False

    def fortify(self, player_id, source_name, target_name, count):
        """
        Déplace 'count' armées de source vers target.
        Si count == 0, le joueur choisit de ne rien faire (passer).
        Cette action termine le tour du joueur.
        """
        # --- CAS 1 : LE JOUEUR PASSE ---
        if count == 0:
            pass
            #print(f"Joueur {player_id} termine son tour sans fortifier.")
            # On ne fait pas de return ici, on laisse le code couler jusqu'à la fin
        
        # --- CAS 2 : LE JOUEUR FORTIFIE ---
        else:
            source = self.map.get_territory(source_name)
            target = self.map.get_territory(target_name)

            # 1. Vérifications de base
            if source.owner != player_id or target.owner != player_id:
                #print("Erreur : Les deux territoires doivent vous appartenir.")
                return False
            
            if source.armies - 1 < count:
                #print(f"Erreur : Pas assez d'armées (Source: {source.armies}, Demandé: {count}). Il faut en laisser 1.")
                return False

            # 2. Vérification du chemin (Pathfinding)
            if not self._check_path(player_id, source, target):
                #print(f"Erreur : Aucun chemin de territoires connectés entre {source_name} et {target_name}.")
                return False

            # 3. Application du mouvement
            source.armies -= count
            target.armies += count
            self._emit(
                "fortify",
                player_id=player_id,
                source=source_name,
                target=target_name,
                count=count,
                source_armies=source.armies,
                target_armies=target.armies,
            )
            #print(f"Fortification : {count} armées déplacées de {source_name} vers {target_name}.")
        if count == 0:
            self._emit("fortify_pass", player_id=player_id)
        
        # --- FIN DE TOUR (COMMUN AUX DEUX CAS) ---
        
        # Gestion de la carte bonus (si conquête)
        self._end_turn_logic(player_id) 

        # Changement de joueur
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        
        return True

    def _end_turn_logic(self, player_id):
        """Logique de fin de tour : piocher une carte si conquête, puis joueur suivant."""
        player = self.players[player_id]
        if player.has_conquered_this_turn:
            card = self.draw_card(player_id)
            #print(f"Fin du tour : Joueur {player_id} reçoit une carte {card}.")
