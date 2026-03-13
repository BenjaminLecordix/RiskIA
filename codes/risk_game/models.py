# risk/models.py
from dataclasses import dataclass, field
from typing import List, Optional, Dict

@dataclass
class Player:
    id: int
    name: str
    color: str
    armies_pool: int = 0  # Armées disponibles à placer (phase de renfort)
    is_alive: bool = True
    cards: List[str] = field(default_factory=list)
    has_conquered_this_turn: bool = False

    def __repr__(self):
        return f"Player {self.id} ({self.name}) | Cards: {len(self.cards)}"

class Territory:
    def __init__(self, name: str, neighbors: List[str], continent: str):
        self.name = name
        self.neighbors = neighbors
        self.continent = continent
        self.owner: Optional[int] = None  # ID du joueur
        self.armies: int = 0

    def __repr__(self):
        owner_str = f"P{self.owner}" if self.owner is not None else "None"
        return f"[{self.name} | Owner: {owner_str} | Armies: {self.armies}]"

class Map:
    def __init__(self, territories_data):
        self.territories: Dict[str, Territory] = {}
        self.continents: Dict[str, List[Territory]] = {} # Nouveau : Cache pour les continents

        for name, data in territories_data.items():
            t = Territory(name, data['neighbors'], data['continent'])
            self.territories[name] = t
            
            # Organisation par continent
            if data['continent'] not in self.continents:
                self.continents[data['continent']] = []
            self.continents[data['continent']].append(t)
    
    def get_territory(self, name):
        return self.territories.get(name)

    def get_all_territories(self):
        return list(self.territories.values())
    
    def get_territories_by_owner(self, player_id):
        return [t for t in self.territories.values() if t.owner == player_id]