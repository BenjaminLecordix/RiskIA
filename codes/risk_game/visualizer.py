# risk_game/visualizer.py
import time
import tkinter as tk
from tkinter import ttk

from .consts import CONTINENT_BONUSES

TERRITORY_COORDS = {
    "Alaska": (0.06, 0.17),
    "Northwest Territory": (0.14, 0.12),
    "Alberta": (0.18, 0.22),
    "Ontario": (0.27, 0.22),
    "Quebec": (0.35, 0.22),
    "Greenland": (0.46, 0.12),
    "Western United States": (0.22, 0.32),
    "Eastern United States": (0.32, 0.32),
    "Central America": (0.26, 0.42),
    "Venezuela": (0.30, 0.52),
    "Peru": (0.30, 0.64),
    "Brazil": (0.40, 0.60),
    "Argentina": (0.34, 0.78),
    "Iceland": (0.52, 0.20),
    "Great Britain": (0.50, 0.28),
    "Scandinavia": (0.58, 0.22),
    "Northern Europe": (0.56, 0.32),
    "Western Europe": (0.50, 0.38),
    "Southern Europe": (0.58, 0.40),
    "Ukraine": (0.66, 0.30),
    "North Africa": (0.52, 0.52),
    "Egypt": (0.60, 0.50),
    "East Africa": (0.66, 0.60),
    "Congo": (0.58, 0.64),
    "South Africa": (0.62, 0.76),
    "Madagascar": (0.72, 0.78),
    "Ural": (0.74, 0.30),
    "Siberia": (0.74, 0.18),
    "Yakutsk": (0.92, 0.14),
    "Kamchatka": (0.98, 0.20),
    "Irkutsk": (0.86, 0.24),
    "Mongolia": (0.84, 0.32),
    "Japan": (0.96, 0.34),
    "Afghanistan": (0.72, 0.38),
    "China": (0.82, 0.40),
    "Middle East": (0.68, 0.50),
    "India": (0.78, 0.48),
    "Southeast Asia": (0.84, 0.54),
    "Indonesia": (0.86, 0.66),
    "New Guinea": (0.94, 0.68),
    "Western Australia": (0.86, 0.82),
    "Eastern Australia": (0.94, 0.82),
}

TERRITORY_LABELS = {
    "Alaska": "AK",
    "Northwest Territory": "NWT",
    "Alberta": "ALB",
    "Ontario": "ONT",
    "Quebec": "QUE",
    "Greenland": "GRL",
    "Western United States": "WUS",
    "Eastern United States": "EUS",
    "Central America": "CAM",
    "Venezuela": "VEN",
    "Peru": "PER",
    "Brazil": "BRA",
    "Argentina": "ARG",
    "Iceland": "ICE",
    "Great Britain": "GBR",
    "Scandinavia": "SCA",
    "Northern Europe": "NEU",
    "Western Europe": "WEU",
    "Southern Europe": "SEU",
    "Ukraine": "UKR",
    "North Africa": "NAF",
    "Egypt": "EGY",
    "East Africa": "EAF",
    "Congo": "CON",
    "South Africa": "SAF",
    "Madagascar": "MAD",
    "Ural": "URL",
    "Siberia": "SIB",
    "Yakutsk": "YAK",
    "Kamchatka": "KAM",
    "Irkutsk": "IRK",
    "Mongolia": "MON",
    "Japan": "JPN",
    "Afghanistan": "AFG",
    "China": "CHN",
    "Middle East": "ME",
    "India": "IND",
    "Southeast Asia": "SEA",
    "Indonesia": "IDN",
    "New Guinea": "NGU",
    "Western Australia": "WAU",
    "Eastern Australia": "EAU",
}

CONTINENT_COLORS = {
    "North America": "#cfe8ff",
    "South America": "#ffe0b5",
    "Europe": "#d9f5d2",
    "Africa": "#ffe6d6",
    "Asia": "#e7ddff",
    "Australia": "#fff7b2",
}

PLAYER_COLORS = {
    0: "#d9534f",
    1: "#2e79d1",
    None: "#c8c8c8",
}


def _convex_hull(points):
    points = sorted(set(points))
    if len(points) <= 1:
        return points

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper = []
    for p in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    return lower[:-1] + upper[:-1]


def _expand_polygon(points, scale=1.12):
    if not points:
        return points
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    expanded = []
    for x, y in points:
        expanded.append((cx + (x - cx) * scale, cy + (y - cy) * scale))
    return expanded


class RiskVisualizer:
    def __init__(
        self,
        engine,
        width=1200,
        height=720,
        node_radius=18,
        update_on_event=True,
        event_delay=0.05,
    ):
        self.engine = engine
        self.width = width
        self.height = height
        self.node_radius = node_radius
        self.update_on_event = update_on_event
        self.event_delay = event_delay
        self._closed = False
        self._turn_counter = 0
        self._event_log = []
        self._max_log = 14
        self._node_items = {}
        self._coords_px = {}

        missing = [t for t in self.engine.map.territories if t not in TERRITORY_COORDS]
        if missing:
            raise ValueError(f"Territoires sans coordonnees: {missing}")

        self.root = tk.Tk()
        self.root.title("Risk - Visualisateur")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.main = ttk.Frame(self.root)
        self.main.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(
            self.main,
            width=self.width,
            height=self.height,
            background="#efece0",
            highlightthickness=0,
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        self.sidebar = ttk.Frame(self.main, width=320)
        self.sidebar.pack(side="right", fill="y")

        self.info_var = tk.StringVar()
        self.info_label = ttk.Label(
            self.sidebar,
            textvariable=self.info_var,
            justify="left",
            wraplength=300,
        )
        self.info_label.pack(padx=12, pady=12, anchor="nw")

        self.legend_label = ttk.Label(
            self.sidebar,
            text="Legende",
            justify="left",
        )
        self.legend_label.pack(padx=12, pady=(8, 4), anchor="nw")

        self.legend_canvas = tk.Canvas(self.sidebar, width=280, height=120, highlightthickness=0)
        self.legend_canvas.pack(padx=12, pady=(0, 12), anchor="nw")

        self.log_label = ttk.Label(self.sidebar, text="Journal", justify="left")
        self.log_label.pack(padx=12, pady=(4, 4), anchor="nw")

        self.log_box = tk.Text(self.sidebar, height=14, width=36, wrap="word", state="disabled")
        self.log_box.pack(padx=12, pady=(0, 12), anchor="nw")

        self.engine.add_listener(self.on_engine_event)
        self._rebuild()
        self.render()

    def _on_close(self):
        self._closed = True
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def is_closed(self):
        return self._closed

    def _on_canvas_resize(self, event):
        if self._closed:
            return
        if event.width == self.width and event.height == self.height:
            return
        self.width = event.width
        self.height = event.height
        self._rebuild()

    def _to_canvas(self, x_norm, y_norm):
        margin_x = 40
        margin_y = 30
        w = max(1, self.width - margin_x * 2)
        h = max(1, self.height - margin_y * 2)
        return margin_x + x_norm * w, margin_y + y_norm * h

    def _rebuild(self):
        self.canvas.delete("all")
        self._node_items = {}
        self._coords_px = {}

        for name, coord in TERRITORY_COORDS.items():
            self._coords_px[name] = self._to_canvas(coord[0], coord[1])

        self._draw_continents()
        self._draw_edges()
        self._draw_nodes()
        self._draw_legend()

    def _draw_continents(self):
        for cont_name, territories in self.engine.map.continents.items():
            pts = []
            for terr in territories:
                pts.append(self._coords_px[terr.name])
            hull = _convex_hull(pts)
            hull = _expand_polygon(hull, scale=1.12)
            if len(hull) >= 3:
                flat = [v for p in hull for v in p]
                fill = CONTINENT_COLORS.get(cont_name, "#dddddd")
                self.canvas.create_polygon(
                    flat,
                    fill=fill,
                    outline="#b8b2a8",
                    width=2,
                    stipple="gray25",
                )
                cx = sum(p[0] for p in hull) / len(hull)
                cy = sum(p[1] for p in hull) / len(hull)
                bonus = CONTINENT_BONUSES.get(cont_name, 0)
                self.canvas.create_text(
                    cx,
                    cy,
                    text=f"{cont_name}\n+{bonus}",
                    font=("Helvetica", 10, "bold"),
                    fill="#4a4034",
                )

    def _draw_edges(self):
        seen = set()
        for name, terr in self.engine.map.territories.items():
            for neigh in terr.neighbors:
                if neigh not in self._coords_px:
                    continue
                key = tuple(sorted((name, neigh)))
                if key in seen:
                    continue
                seen.add(key)
                x1, y1 = self._coords_px[name]
                x2, y2 = self._coords_px[neigh]
                intercontinental = (
                    self.engine.map.territories[name].continent
                    != self.engine.map.territories[neigh].continent
                )
                self.canvas.create_line(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill="#7c6f63" if intercontinental else "#9e9387",
                    width=2 if intercontinental else 1,
                    dash=(4, 3) if intercontinental else None,
                )

    def _draw_nodes(self):
        for name in self.engine.map.territories:
            x, y = self._coords_px[name]
            r = self.node_radius
            circle_id = self.canvas.create_oval(
                x - r,
                y - r,
                x + r,
                y + r,
                fill=PLAYER_COLORS[None],
                outline="#2f2f2f",
                width=1,
            )
            army_id = self.canvas.create_text(
                x,
                y,
                text="0",
                font=("Helvetica", 10, "bold"),
                fill="#ffffff",
            )
            label_id = self.canvas.create_text(
                x,
                y + r + 8,
                text=TERRITORY_LABELS.get(name, name),
                font=("Helvetica", 8),
                fill="#3a3228",
            )
            self._node_items[name] = (circle_id, army_id, label_id)

    def _draw_legend(self):
        self.legend_canvas.delete("all")
        x = 8
        y = 10
        for player_id, label in [(0, "Joueur 0 (IA)"), (1, "Joueur 1 (Bot)"), (None, "Neutre")]:
            color = PLAYER_COLORS[player_id]
            self.legend_canvas.create_oval(x, y, x + 16, y + 16, fill=color, outline="#333333")
            self.legend_canvas.create_text(
                x + 24,
                y + 8,
                text=label,
                anchor="w",
                font=("Helvetica", 9),
                fill="#2c241d",
            )
            y += 24

    def _update_nodes(self):
        for name, terr in self.engine.map.territories.items():
            circle_id, army_id, _ = self._node_items[name]
            owner = terr.owner
            fill = PLAYER_COLORS.get(owner, PLAYER_COLORS[None])
            text_color = "#111111" if owner is None else "#ffffff"
            outline = "#1e1e1e"
            width = 2 if owner == self.engine.current_player_index else 1

            self.canvas.itemconfigure(circle_id, fill=fill, outline=outline, width=width)
            self.canvas.itemconfigure(army_id, text=str(terr.armies), fill=text_color)

    def _update_info(self):
        current = self.engine.players[self.engine.current_player_index]
        terr_count = len(self.engine.map.get_territories_by_owner(current.id))
        info_lines = [
            f"Tour: {self._turn_counter}",
            f"Phase: {self.engine.phase}",
            f"Joueur courant: P{current.id} ({current.name})",
            f"Pool renforts: {current.armies_pool}",
            f"Territoires: {terr_count}",
            f"Cartes: {len(current.cards)}",
        ]
        self.info_var.set("\n".join(info_lines))

    def _update_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        for line in self._event_log[-self._max_log :]:
            self.log_box.insert("end", line + "\n")
        self.log_box.configure(state="disabled")

    def render(self):
        if self._closed:
            return False
        self._update_nodes()
        self._update_info()
        self._update_log()
        try:
            self.root.update_idletasks()
            self.root.update()
        except tk.TclError:
            self._closed = True
            return False
        return True

    def on_engine_event(self, event):
        if event.get("type") == "start_turn":
            self._turn_counter += 1
        message = self._format_event(event)
        if message:
            self._event_log.append(message)
        if self.update_on_event and not self._closed:
            self.render()
            if self.event_delay > 0:
                time.sleep(self.event_delay)

    def _format_event(self, event):
        etype = event.get("type")
        if etype == "reset":
            return "Nouvelle partie."
        if etype == "start_turn":
            pid = event.get("player_id")
            income = event.get("income", 0)
            card_income = event.get("card_income", 0)
            extra = f"+{card_income}" if card_income else "0"
            return f"Tour {self._turn_counter} | P{pid} renforts +{income} (cartes {extra})"
        if etype == "place":
            pid = event.get("player_id")
            terr = event.get("territory")
            amount = event.get("amount")
            return f"P{pid} renforce {TERRITORY_LABELS.get(terr, terr)} +{amount}"
        if etype == "trade":
            pid = event.get("player_id")
            reward = event.get("reward")
            return f"P{pid} echange cartes -> +{reward} renforts"
        if etype == "attack":
            pid = event.get("player_id")
            src = TERRITORY_LABELS.get(event.get("source"), event.get("source"))
            tgt = TERRITORY_LABELS.get(event.get("target"), event.get("target"))
            success = event.get("success")
            aloss = event.get("attacker_losses", 0)
            dloss = event.get("defender_losses", 0)
            outcome = "gagne" if success else "echoue"
            return f"P{pid} attaque {src}->{tgt} : {outcome} (A-{aloss}/D-{dloss})"
        if etype == "fortify":
            pid = event.get("player_id")
            src = TERRITORY_LABELS.get(event.get("source"), event.get("source"))
            tgt = TERRITORY_LABELS.get(event.get("target"), event.get("target"))
            count = event.get("count")
            return f"P{pid} fortifie {src}->{tgt} (+{count})"
        if etype == "fortify_pass":
            pid = event.get("player_id")
            return f"P{pid} passe la fortification"
        if etype == "elimination":
            pid = event.get("player_id")
            return f"P{pid} elimine"
        return None
