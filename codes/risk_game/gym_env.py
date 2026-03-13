# risk_game/gym_env.py

import os
import random

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .ai import AggressiveBot, NaiveBot, RandomBot
from .engine import RiskEngine

np.seterr(all="raise")


class RiskGymEnv(gym.Env):
    """
    Environnement Gymnasium pour le jeu Risk (1v1).
    - Joueur 0 : Agent RL
    - Joueur 1 : Adversaire scripté ou self-play
    """

    metadata = {"render_modes": ["human"], "render_fps": 4}
    _selfplay_model_cache = {}

    def __init__(
        self,
        render_mode=None,
        opponent_mode="naive",
        opponent_pool=None,
        selfplay_models=None,
        selfplay_deterministic=False,
        selfplay_max_actions=2048,
    ):
        super().__init__()
        self.render_mode = render_mode
        self.opponent_mode = opponent_mode
        self.opponent_pool = opponent_pool or {
            "naive": 0.5,
            "aggressive": 0.3,
            "random": 0.2,
        }
        self.selfplay_model_paths = self._resolve_selfplay_paths(selfplay_models or [])
        self.selfplay_deterministic = selfplay_deterministic
        self.selfplay_max_actions = selfplay_max_actions

        # 1. Initialisation du moteur et de l'adversaire
        self.engine = RiskEngine(num_players=2)
        self.player_id = 0
        self.opponent_id = 1
        self.opponent_kind = None
        self.opponent_bot = None
        self.opponent_model = None
        self._set_episode_opponent()

        # 2. Construction de la carte et des index
        self.territory_names = sorted(list(self.engine.map.territories.keys()))
        self.terr_to_idx = {name: i for i, name in enumerate(self.territory_names)}

        # 3. Construction de la liste des arêtes
        self.edge_list = []
        for name in self.territory_names:
            src_id = self.terr_to_idx[name]
            territory = self.engine.map.territories[name]
            for neighbor_name in territory.neighbors:
                if neighbor_name in self.terr_to_idx:
                    tgt_id = self.terr_to_idx[neighbor_name]
                    self.edge_list.append((src_id, tgt_id))

        # 4. Espaces Gym
        self.n_territories = 42
        self.n_edges = len(self.edge_list)
        self.action_space_size = self.n_territories + 1 + self.n_edges
        self.action_space = spaces.Discrete(self.action_space_size)

        # Observation : 42 (owner) + 42 (armies) + 5 (meta) = 89
        self.observation_space = spaces.Box(low=-1, high=1000, shape=(89,), dtype=np.float32)

    @staticmethod
    def _normalize_model_path(model_path):
        if model_path.endswith(".zip"):
            return model_path if os.path.exists(model_path) else None
        zipped = f"{model_path}.zip"
        if os.path.exists(zipped):
            return zipped
        if os.path.exists(model_path):
            return model_path
        return None

    def _resolve_selfplay_paths(self, model_paths):
        resolved = []
        for path in model_paths:
            normalized = self._normalize_model_path(path)
            if normalized and normalized not in resolved:
                resolved.append(normalized)
        return resolved

    @classmethod
    def _load_selfplay_model(cls, model_path):
        from sb3_contrib import MaskablePPO

        normalized = cls._normalize_model_path(model_path)
        if normalized is None:
            raise FileNotFoundError(f"Modèle self-play introuvable: {model_path}")

        mtime = os.path.getmtime(normalized)
        cached = cls._selfplay_model_cache.get(normalized)
        if cached and cached["mtime"] == mtime:
            return cached["model"]

        model = MaskablePPO.load(normalized)
        cls._selfplay_model_cache[normalized] = {"model": model, "mtime": mtime}
        return model

    def action_masks(self):
        """
        Retourne un masque booléen des actions valides pour le joueur RL.
        """
        return self._action_masks_for_player(self.player_id)

    def _action_masks_for_player(self, player_id):
        mask = [False] * self.action_space_size
        player = self.engine.players[player_id]

        if not player.is_alive or self.engine.current_player_index != player_id:
            raise RuntimeError(
                f"EMPTY MASK | phase={self.engine.phase} "
                f"current={self.engine.current_player_index} "
                f"alive={player.is_alive} player={player_id}"
            )

        phase = self.engine.phase

        if phase == "REINFORCE":
            for i in range(self.n_territories):
                terr_name = self.territory_names[i]
                terr = self.engine.map.territories[terr_name]
                if terr.owner == player_id:
                    mask[i] = True

        elif phase == "ATTACK":
            mask[self.n_territories] = True
            for idx, (src_id, tgt_id) in enumerate(self.edge_list):
                src_name = self.territory_names[src_id]
                tgt_name = self.territory_names[tgt_id]
                src = self.engine.map.territories[src_name]
                tgt = self.engine.map.territories[tgt_name]
                if src.owner == player_id and tgt.owner != player_id and src.armies > 1:
                    action_idx = self.n_territories + 1 + idx
                    mask[action_idx] = True

        elif phase == "FORTIFY":
            mask[self.n_territories] = True
            for idx, (src_id, tgt_id) in enumerate(self.edge_list):
                src_name = self.territory_names[src_id]
                tgt_name = self.territory_names[tgt_id]
                src = self.engine.map.territories[src_name]
                tgt = self.engine.map.territories[tgt_name]
                if src.owner == player_id and tgt.owner == player_id and src.armies > 1:
                    action_idx = self.n_territories + 1 + idx
                    mask[action_idx] = True

        else:
            mask[self.n_territories] = True

        mask = np.array(mask, dtype=np.bool_)
        if not np.any(mask):
            raise RuntimeError(
                f"EMPTY MASK | phase={self.engine.phase} "
                f"current={self.engine.current_player_index} "
                f"alive={player.is_alive} player={player_id}"
            )
        return mask

    def _set_episode_opponent(self):
        """
        Choisit et instancie l'adversaire de l'épisode.
        Modes:
        - naive/aggressive/random
        - selfplay (modèle RL)
        - pool (tirage pondéré)
        """
        mode = self.opponent_mode
        if mode == "pool":
            kinds = list(self.opponent_pool.keys())
            weights = list(self.opponent_pool.values())
            kind = random.choices(kinds, weights=weights, k=1)[0]
        else:
            kind = mode

        self.opponent_kind = kind
        self.opponent_bot = None
        self.opponent_model = None

        if kind == "naive":
            self.opponent_bot = NaiveBot(self.engine, self.opponent_id)
            return
        if kind == "aggressive":
            self.opponent_bot = AggressiveBot(self.engine, self.opponent_id)
            return
        if kind == "random":
            self.opponent_bot = RandomBot(self.engine, self.opponent_id)
            return
        if kind == "selfplay":
            if not self.selfplay_model_paths:
                raise ValueError(
                    "selfplay demandé mais aucun modèle valide trouvé. "
                    "Passer selfplay_models=[...]."
                )
            chosen_path = random.choice(self.selfplay_model_paths)
            self.opponent_model = self._load_selfplay_model(chosen_path)
            return

        raise ValueError(
            f"opponent_mode invalide: {self.opponent_mode}. "
            "Utiliser naive/aggressive/random/selfplay/pool."
        )

    def _apply_action_for_player(self, player_id, action, shape_rewards=False):
        reward_delta = 0.0
        action = int(action)

        if action < self.n_territories:
            terr_name = self.territory_names[action]
            if self.engine.phase == "REINFORCE":
                self.engine.place_armies(player_id, terr_name, 1)
                if self.engine.players[player_id].armies_pool <= 0:
                    self.engine.phase = "ATTACK"
            return reward_delta

        if action == self.n_territories:
            if self.engine.phase == "ATTACK":
                self.engine.phase = "FORTIFY"
            elif self.engine.phase == "FORTIFY":
                self.engine.fortify(player_id, None, None, 0)
            return reward_delta

        edge_idx = action - (self.n_territories + 1)
        if not (0 <= edge_idx < len(self.edge_list)):
            return reward_delta

        src_id, tgt_id = self.edge_list[edge_idx]
        src_name = self.territory_names[src_id]
        tgt_name = self.territory_names[tgt_id]

        if self.engine.phase == "ATTACK":
            if shape_rewards and player_id == self.player_id:
                prev_armies_gap = self._get_armies_gap()
                prev_territories = self._get_territory_count()
                prev_gap = self._get_income_gap()
                self.engine.attack(player_id, src_name, tgt_name)
                current_armies_gap = self._get_armies_gap()
                current_territories = self._get_territory_count()
                current_gap = self._get_income_gap()
                reward_delta += (
                    (current_armies_gap - prev_armies_gap) * 0.25
                    + (current_territories - prev_territories) * 0.10
                    + (current_gap - prev_gap) * 0.25
                )
            else:
                self.engine.attack(player_id, src_name, tgt_name)
            return reward_delta

        if self.engine.phase == "FORTIFY":
            src_terr = self.engine.map.territories[src_name]
            nb_to_move = src_terr.armies - 1
            if nb_to_move > 0:
                self.engine.fortify(player_id, src_name, tgt_name, nb_to_move)
            else:
                self.engine.fortify(player_id, None, None, 0)
            return reward_delta

        return reward_delta

    def _play_selfplay_turn(self):
        if self.opponent_model is None:
            raise RuntimeError("Mode self-play actif sans modèle adversaire.")

        for _ in range(self.selfplay_max_actions):
            if not self.engine.players[self.opponent_id].is_alive:
                return
            if self.engine.current_player_index != self.opponent_id:
                return

            obs = self._get_obs_for_player(self.opponent_id)
            mask = self._action_masks_for_player(self.opponent_id)
            action, _ = self.opponent_model.predict(
                obs,
                action_masks=mask,
                deterministic=self.selfplay_deterministic,
            )
            action = int(action)

            if action < 0 or action >= self.action_space_size or not mask[action]:
                valid = np.flatnonzero(mask)
                if len(valid) == 0:
                    raise RuntimeError("Self-play: aucun coup valide")
                action = int(np.random.choice(valid))

            self._apply_action_for_player(self.opponent_id, action, shape_rewards=False)

        raise RuntimeError(
            "Self-play: nombre max d'actions dépassé sur un tour adversaire "
            f"({self.selfplay_max_actions})."
        )

    def _play_opponent_turn(self):
        if not self.engine.players[self.opponent_id].is_alive:
            return

        self.engine.current_player_index = self.opponent_id
        self.engine.start_turn()

        if self.opponent_kind == "selfplay":
            self._play_selfplay_turn()
        else:
            self.opponent_bot.play_turn()

        if self.engine.players[self.player_id].is_alive:
            self.engine.current_player_index = self.player_id
            self.engine.start_turn()

    def step(self, action):
        """
        Exécute l'action choisie par l'agent RL (joueur 0).
        """
        reward = -0.01
        terminated = False
        truncated = False

        reward += self._apply_action_for_player(self.player_id, action, shape_rewards=True)

        # Si le tour RL est fini, on joue le tour adversaire complet.
        if (
            self.engine.players[self.player_id].is_alive
            and self.engine.current_player_index == self.opponent_id
        ):
            self._play_opponent_turn()

        # Vérification fin de partie.
        living = [p for p in self.engine.players if p.is_alive]
        if len(living) == 1:
            terminated = True
            if living[0].id == self.player_id:
                reward += 250
            else:
                reward -= 250

        obs = self._get_obs()
        if np.isnan(obs).any():
            raise RuntimeError("NaN in observation")
        if np.isinf(obs).any():
            raise RuntimeError("Inf in observation")

        return obs, reward, terminated, truncated, {}

    def _get_income_gap(self):
        income_self = self.engine.calculate_reinforcements(self.player_id)
        income_opp = self.engine.calculate_reinforcements(self.opponent_id)
        return income_self - income_opp

    def _get_armies_gap(self):
        count_self = sum(
            t.armies for t in self.engine.map.territories.values() if t.owner == self.player_id
        )
        count_opp = sum(
            t.armies for t in self.engine.map.territories.values() if t.owner == self.opponent_id
        )
        return count_self - count_opp

    def _get_territory_count(self):
        return sum(1 for t in self.engine.map.territories.values() if t.owner == self.player_id)

    def _get_obs_for_player(self, player_id):
        other_id = self.opponent_id if player_id == self.player_id else self.player_id

        owners = []
        for name in self.territory_names:
            t = self.engine.map.territories[name]
            if t.owner == player_id:
                owners.append(1.0)
            elif t.owner == other_id:
                owners.append(-1.0)
            else:
                owners.append(0.0)

        armies = []
        for name in self.territory_names:
            t = self.engine.map.territories[name]
            armies.append(t.armies / 100.0)

        phase_val = 0.0
        if self.engine.phase == "ATTACK":
            phase_val = 0.5
        elif self.engine.phase == "FORTIFY":
            phase_val = 1.0

        p_me = self.engine.players[player_id]
        p_op = self.engine.players[other_id]
        meta = [
            phase_val,
            p_me.armies_pool / 20.0,
            p_op.armies_pool / 20.0,
            len(p_me.cards) / 5.0,
            len(p_op.cards) / 5.0,
        ]

        return np.concatenate([owners, armies, meta], dtype=np.float32)

    def _get_obs(self):
        return self._get_obs_for_player(self.player_id)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)

        # Le bot (joueur 1) commence systématiquement.
        # Retry de sécurité si élimination de l'IA sur l'ouverture.
        max_retries = 10
        for _ in range(max_retries):
            self.engine.reset()
            self._set_episode_opponent()
            self._play_opponent_turn()

            if self.engine.players[self.player_id].is_alive:
                return self._get_obs(), {}

        raise RuntimeError(
            "Impossible d'initialiser un épisode valide: l'IA a été éliminée "
            "au tour d'ouverture du bot sur tous les retries."
        )
