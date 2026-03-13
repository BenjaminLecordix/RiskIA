# risk_game/ai.py
import random
from collections import Counter
from .consts import CARD_INFANTRY, CARD_CAVALRY, CARD_ARTILLERY
from .models import Territory

class NaiveBot:
    def __init__(self, engine, player_id):
        self.engine = engine
        self.player_id = player_id

    @property
    def player(self):
        return self.engine.players[self.player_id]

    @property
    def map(self):
        return self.engine.map

    def play_turn(self):
        """Orchestre le tour complet du Bot"""
        if not self.player.is_alive:
            return

        #print(f"\n--- TOUR BOT ({self.player.name}) ---")
        
        # 0. Début de tour (calcul renforts passifs)
        # Note: Dans notre engine, start_turn() est appelé par la boucle de jeu principale, 
        # mais ici on assume qu'on est DANS le tour.
        
        # 1. Placement des renforts
        self._phase_place_armies()
        
        # 2. Échange de cartes
        self._phase_trade_cards()
        
        # 3. Attaques
        self._phase_attack()
        
        # 4. Fortification
        self._phase_fortify()

    # --- LOGIQUE D'ANALYSE ---

    def _get_continent_ownership(self):
        """Retourne un dict {continent: pourcentage_possession}"""
        stats = {}
        for cont_name, territories in self.map.continents.items():
            owned = sum(1 for t in territories if t.owner == self.player_id)
            total = len(territories)
            stats[cont_name] = owned / total
        return stats

    def _is_border_territory(self, territory):
        """Vrai si le territoire a au moins un voisin ennemi"""
        for n_name in territory.neighbors:
            neighbor = self.map.get_territory(n_name)
            if neighbor.owner != self.player_id:
                return True
        return False

    # --- PHASE 1 : CARTES ---
    
    def _phase_trade_cards(self):
        """Règle : Échanger dès que possible"""
        while self.engine.can_trade(self.player_id):
            cards = self.player.cards
            # Recherche naïve de combinaison valide (3 identiques ou 1 de chaque)
            counts = Counter(cards)
            indices_to_trade = []
            
            # Cas A: 3 identiques
            for c_type in [CARD_INFANTRY, CARD_CAVALRY, CARD_ARTILLERY]:
                if counts[c_type] >= 3:
                    # Trouver les indices des 3 premières cartes de ce type
                    indices_to_trade = [i for i, c in enumerate(cards) if c == c_type][:3]
                    break
            
            # Cas B: 1 de chaque
            if not indices_to_trade and counts[CARD_INFANTRY] >= 1 and counts[CARD_CAVALRY] >= 1 and counts[CARD_ARTILLERY] >= 1:
                idx_inf = cards.index(CARD_INFANTRY)
                idx_cav = cards.index(CARD_CAVALRY)
                idx_art = cards.index(CARD_ARTILLERY)
                indices_to_trade = [idx_inf, idx_cav, idx_art]
            
            if indices_to_trade:
                #print(f"Bot échange des cartes (indices {indices_to_trade})")
                self.engine.trade_cards(self.player_id, indices_to_trade)
            else:
                # On a 3 cartes mais pas de combo valide (ex: 2 Inf, 1 Cav)
                break

    # --- PHASE 2 : RENFORTS ---

    def _phase_place_armies(self):
        """
        Règle : Dans le continent le plus susceptible d'être possédé (Max %),
        sur un voisin d'un territoire non possédé (Frontière).
        """
        while self.player.armies_pool > 0:
            stats = self._get_continent_ownership()
            
            # Filtrer les continents qu'on ne possède pas encore à 100% (si possible)
            # On trie par pourcentage décroissant
            sorted_conts = sorted(stats.items(), key=lambda x: x[1], reverse=True)
            
            target_territory = None
            
            # On cherche le meilleur continent
            for cont_name, pct in sorted_conts:
                if pct >= 1.0: continue # Déjà conquis, pas prioritaire pour la conquête
                
                # Chercher un territoire frontière dans ce continent
                candidates = []
                continent_territories = self.map.continents[cont_name]
                for t in continent_territories:
                    if t.owner == self.player_id and self._is_border_territory(t):
                        candidates.append(t)
                
                if candidates:
                    # On prend le premier (ou on pourrait prendre celui qui a le plus d'ennemis)
                    target_territory = candidates[0]
                    break
            
            # Fallback : Si on possède tout ou rien, on renforce n'importe quelle frontière
            if not target_territory:
                all_my_terrs = self.map.get_territories_by_owner(self.player_id)
                borders = [t for t in all_my_terrs if self._is_border_territory(t)]
                if borders:
                    target_territory = random.choice(borders)
                else:
                    # Cas extrême : on a gagné ou on est isolé
                    target_territory = all_my_terrs[0]

            # On place tout d'un coup ou 1 par 1 ? Faisons tout d'un coup pour simplifier
            amount = self.player.armies_pool
            self.engine.place_armies(self.player_id, target_territory.name, amount)
            #print(f"Bot renforce {target_territory.name} (+{amount})")

    # --- PHASE 3 : ATTAQUE ---

    def _phase_attack(self):
        """
        Règle : Attaquer pour se rapprocher de la capture d'un continent.
        Cible : Territoire ennemi dans mon continent prioritaire.
        """
        can_attack_more = True
        while can_attack_more:
            # Réévaluer la stratégie à chaque attaque (le plateau change)
            stats = self._get_continent_ownership()
            # On vise le continent presque fini (non 100%)
            sorted_conts = sorted(stats.items(), key=lambda x: x[1], reverse=True)
            
            attack_executed = False
            
            for cont_name, pct in sorted_conts:
                if pct >= 1.0: continue 

                # Identifier les cibles ennemies dans ce continent
                target_continent_territories = self.map.continents[cont_name]
                enemy_targets = [t for t in target_continent_territories if t.owner != self.player_id]
                
                # Chercher si on peut attaquer un de ces ennemis
                for target in enemy_targets:
                    # Trouver mes voisins capables d'attaquer ce target
                    for neighbor_name in target.neighbors:
                        my_source = self.map.get_territory(neighbor_name)
                        
                        # Conditions : C'est à moi, et j'ai assez de troupes (> target + 1 pour être sûr)
                        if my_source.owner == self.player_id and my_source.armies > target.armies + 1:
                            success = self.engine.attack(self.player_id, my_source.name, target.name)
                            attack_executed = True
                            if success:
                                # On a conquis ! On arrête cette boucle pour réévaluer
                                pass
                            break # On sort de la boucle targets
                    if attack_executed: break # On sort de la boucle continents
                if attack_executed: break

            # Si aucune attaque n'a été faite dans cette boucle, on arrête
            if not attack_executed:
                can_attack_more = False

    # --- PHASE 4 : FORTIFICATION ---

    def _phase_fortify(self):
        """
        Règle : Source = Intérieur (non frontalier) avec le plus de troupes.
                Destination = Frontalier.
        """
        my_terrs = self.map.get_territories_by_owner(self.player_id)
        
        # 1. Identifier Sources (Intérieur, > 1 armée)
        interior_sources = [t for t in my_terrs if not self._is_border_territory(t) and t.armies > 1]
        # Trier par nombre d'armées décroissant
        interior_sources.sort(key=lambda t: t.armies, reverse=True)
        
        if not interior_sources:
            self.engine.fortify(self.player_id, None, None, 0) # Passer
            return

        best_source = interior_sources[0]
        
        # 2. Identifier Destination (Frontière)
        # On cherche une frontière accessible
        destinations = [t for t in my_terrs if self._is_border_territory(t)]
        
        target_dest = None
        for dest in destinations:
            if dest == best_source: continue
            # Vérifier le chemin
            if self.engine._check_path(self.player_id, best_source, dest):
                target_dest = dest
                break # On prend le premier trouvé
        
        if target_dest:
            # On déplace tout sauf 1
            amount = best_source.armies - 1
            self.engine.fortify(self.player_id, best_source.name, target_dest.name, amount)
        else:
            self.engine.fortify(self.player_id, None, None, 0)


class RandomBot(NaiveBot):
    """Bot baseline aléatoire pour diversifier l'entraînement."""

    def _phase_place_armies(self):
        my_terrs = self.map.get_territories_by_owner(self.player_id)
        if not my_terrs:
            return
        while self.player.armies_pool > 0:
            target = random.choice(my_terrs)
            self.engine.place_armies(self.player_id, target.name, 1)

    def _phase_attack(self):
        # Attaques aléatoires, avec arrêt probabiliste pour varier le style.
        while True:
            options = []
            for src in self.map.get_territories_by_owner(self.player_id):
                if src.armies <= 1:
                    continue
                for neighbor_name in src.neighbors:
                    tgt = self.map.get_territory(neighbor_name)
                    if tgt.owner != self.player_id:
                        options.append((src, tgt))
            if not options:
                break

            src, tgt = random.choice(options)
            self.engine.attack(self.player_id, src.name, tgt.name)

            if random.random() < 0.45:
                break

    def _phase_fortify(self):
        my_terrs = self.map.get_territories_by_owner(self.player_id)
        sources = [t for t in my_terrs if t.armies > 1]
        if not sources:
            self.engine.fortify(self.player_id, None, None, 0)
            return

        random.shuffle(sources)
        for source in sources:
            targets = [t for t in my_terrs if t != source]
            random.shuffle(targets)
            for target in targets:
                if self.engine._check_path(self.player_id, source, target):
                    amount = max(1, source.armies // 2)
                    amount = min(amount, source.armies - 1)
                    self.engine.fortify(self.player_id, source.name, target.name, amount)
                    return

        self.engine.fortify(self.player_id, None, None, 0)


class AggressiveBot(NaiveBot):
    """Bot plus offensif: maximise les attaques à avantage positif."""

    def _phase_place_armies(self):
        my_terrs = self.map.get_territories_by_owner(self.player_id)
        if not my_terrs:
            return

        # Priorité aux frontières avec forte pression ennemie.
        def border_pressure(t):
            pressure = 0
            for n_name in t.neighbors:
                n = self.map.get_territory(n_name)
                if n.owner != self.player_id:
                    pressure += n.armies
            return pressure

        while self.player.armies_pool > 0:
            target = max(my_terrs, key=border_pressure)
            self.engine.place_armies(self.player_id, target.name, 1)

    def _phase_attack(self):
        while True:
            best_option = None
            best_margin = -10**9

            for src in self.map.get_territories_by_owner(self.player_id):
                if src.armies <= 1:
                    continue
                for n_name in src.neighbors:
                    tgt = self.map.get_territory(n_name)
                    if tgt.owner == self.player_id:
                        continue
                    margin = src.armies - tgt.armies
                    if margin > best_margin:
                        best_margin = margin
                        best_option = (src, tgt, margin)

            if best_option is None:
                break

            src, tgt, margin = best_option
            # Évite les attaques trop défavorables.
            if margin <= 0:
                break

            self.engine.attack(self.player_id, src.name, tgt.name)

            # Si l'avantage devient faible, on arrête pour préserver les troupes.
            if margin <= 2:
                break

    def _phase_fortify(self):
        my_terrs = self.map.get_territories_by_owner(self.player_id)
        if not my_terrs:
            self.engine.fortify(self.player_id, None, None, 0)
            return

        frontiers = [t for t in my_terrs if self._is_border_territory(t)]
        interiors = [t for t in my_terrs if not self._is_border_territory(t) and t.armies > 1]
        interiors.sort(key=lambda t: t.armies, reverse=True)

        if not frontiers or not interiors:
            self.engine.fortify(self.player_id, None, None, 0)
            return

        for source in interiors:
            target = max(frontiers, key=lambda t: t.armies)
            if source != target and self.engine._check_path(self.player_id, source, target):
                amount = source.armies - 1
                self.engine.fortify(self.player_id, source.name, target.name, amount)
                return

        self.engine.fortify(self.player_id, None, None, 0)
