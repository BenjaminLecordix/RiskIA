# risk/consts.py

# Bonus de troupes par tour si un joueur possède tout le continent
CONTINENT_BONUSES = {
    "North America": 5,
    "South America": 2,
    "Europe": 5,
    "Africa": 3,
    "Asia": 7,
    "Australia": 2
}

# Nombre d'armées de départ selon le nombre de joueurs (Règles classiques)
# 2 joueurs -> 40 armées chacun
STARTING_ARMIES = {
    2: 40,
    3: 35,
    4: 30,
    5: 25,
    6: 20
}

# Ta définition de la carte
TERRITORIES_DATA = {
    "Alaska": {"neighbors": ["Northwest Territory", "Alberta", "Kamchatka"], "continent": "North America"},
    "Northwest Territory": {"neighbors": ["Alaska", "Alberta", "Ontario", "Greenland"], "continent": "North America"},
    "Alberta": {"neighbors": ["Alaska", "Northwest Territory", "Ontario", "Western United States"], "continent": "North America"},
    "Ontario": {"neighbors": ["Northwest Territory", "Alberta", "Western United States", "Eastern United States", "Quebec", "Greenland"], "continent": "North America"},
    "Quebec": {"neighbors": ["Ontario", "Eastern United States", "Greenland"], "continent": "North America"},
    "Greenland": {"neighbors": ["Northwest Territory", "Ontario", "Quebec", "Iceland"], "continent": "North America"},
    "Western United States": {"neighbors": ["Alberta", "Ontario", "Eastern United States", "Central America"], "continent": "North America"},
    "Eastern United States": {"neighbors": ["Ontario", "Quebec", "Western United States", "Central America"], "continent": "North America"},
    "Central America": {"neighbors": ["Western United States", "Eastern United States", "Venezuela"], "continent": "North America"},
    "Venezuela": {"neighbors": ["Central America", "Peru", "Brazil"], "continent": "South America"},
    "Peru": {"neighbors": ["Venezuela", "Brazil", "Argentina"], "continent": "South America"},
    "Brazil": {"neighbors": ["Venezuela", "Peru", "Argentina", "North Africa"], "continent": "South America"},
    "Argentina": {"neighbors": ["Peru", "Brazil"], "continent": "South America"},
    "Iceland": {"neighbors": ["Greenland", "Great Britain", "Scandinavia"], "continent": "Europe"},
    "Great Britain": {"neighbors": ["Iceland", "Scandinavia", "Northern Europe", "Western Europe"], "continent": "Europe"},
    "Scandinavia": {"neighbors": ["Iceland", "Great Britain", "Northern Europe", "Ukraine"], "continent": "Europe"},
    "Ukraine": {"neighbors": ["Scandinavia", "Northern Europe", "Southern Europe", "Ural", "Afghanistan", "Middle East"], "continent": "Europe"},
    "Northern Europe": {"neighbors": ["Great Britain", "Scandinavia", "Ukraine", "Southern Europe", "Western Europe"], "continent": "Europe"},
    "Western Europe": {"neighbors": ["Great Britain", "Northern Europe", "Southern Europe", "North Africa"], "continent": "Europe"},
    "Southern Europe": {"neighbors": ["Western Europe", "Northern Europe", "Ukraine", "Middle East", "Egypt", "North Africa"], "continent": "Europe"},
    "North Africa": {"neighbors": ["Western Europe", "Southern Europe", "Egypt", "East Africa", "Congo", "Brazil"], "continent": "Africa"},
    "Egypt": {"neighbors": ["North Africa", "Southern Europe", "Middle East", "East Africa"], "continent": "Africa"},
    "East Africa": {"neighbors": ["Egypt", "North Africa", "Congo", "South Africa", "Madagascar", "Middle East"], "continent": "Africa"},
    "Congo": {"neighbors": ["North Africa", "East Africa", "South Africa"], "continent": "Africa"},
    "South Africa": {"neighbors": ["Congo", "East Africa", "Madagascar"], "continent": "Africa"},
    "Madagascar": {"neighbors": ["East Africa", "South Africa"], "continent": "Africa"},
    "Ural": {"neighbors": ["Ukraine", "Afghanistan", "China", "Siberia"], "continent": "Asia"},
    "Siberia": {"neighbors": ["Ural", "China", "Mongolia", "Irkutsk", "Yakutsk"], "continent": "Asia"},
    "Yakutsk": {"neighbors": ["Siberia", "Irkutsk", "Kamchatka"], "continent": "Asia"},
    "Kamchatka": {"neighbors": ["Yakutsk", "Irkutsk", "Mongolia", "Japan", "Alaska"], "continent": "Asia"},
    "Irkutsk": {"neighbors": ["Siberia", "Yakutsk", "Kamchatka", "Mongolia"], "continent": "Asia"},
    "Mongolia": {"neighbors": ["Siberia", "China", "Irkutsk", "Kamchatka", "Japan"], "continent": "Asia"},
    "Japan": {"neighbors": ["Mongolia", "Kamchatka"], "continent": "Asia"},
    "Afghanistan": {"neighbors": ["Ukraine", "Ural", "India", "China", "Middle East"], "continent": "Asia"},
    "China": {"neighbors": ["Ural", "Afghanistan", "Mongolia", "Southeast Asia", "India", "Siberia"], "continent": "Asia"},
    "Middle East": {"neighbors": ["Ukraine", "Southern Europe", "Egypt", "East Africa", "India", "Afghanistan"], "continent": "Asia"},
    "India": {"neighbors": ["Middle East", "Afghanistan", "China", "Southeast Asia"], "continent": "Asia"},
    "Southeast Asia": {"neighbors": ["India", "China", "Indonesia"], "continent": "Asia"},
    "Indonesia": {"neighbors": ["Southeast Asia", "New Guinea", "Western Australia"], "continent": "Australia"},
    "New Guinea": {"neighbors": ["Indonesia", "Western Australia", "Eastern Australia"], "continent": "Australia"},
    "Western Australia": {"neighbors": ["Indonesia", "New Guinea", "Eastern Australia"], "continent": "Australia"},
    "Eastern Australia": {"neighbors": ["New Guinea", "Western Australia"], "continent": "Australia"}
}


# Types de cartes
CARD_INFANTRY = "Infantry"
CARD_CAVALRY = "Cavalry"
CARD_ARTILLERY = "Artillery"

CARD_TYPES = [CARD_INFANTRY, CARD_CAVALRY, CARD_ARTILLERY]

# Récompenses d'échange (Selon tes règles spécifiques)
TRADE_REWARDS = {
    "3_INFANTRY": 4,
    "3_CAVALRY": 6,
    "3_ARTILLERY": 8,
    "1_EACH": 10  # Un de chaque type
}

# Limite de cartes en main avant obligation d'échange
MAX_CARDS_HAND = 5