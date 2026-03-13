import math
import os
import random
import time

import numpy as np
import torch
from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.utils import get_action_masks
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.callbacks import BaseCallback, CallbackList, CheckpointCallback
from stable_baselines3.common.utils import get_schedule_fn
from torch.distributions import Distribution

from risk_game.gym_env import RiskGymEnv

np.seterr(all="raise")


def mask_fn(env):
    """Fonction helper pour extraire les masques de l'environnement."""
    return env.action_masks()


class FinitePolicyCallback(BaseCallback):
    """Stoppe l'entraînement si des paramètres non finis apparaissent."""

    def _on_step(self):
        return True

    def _on_rollout_end(self):
        assert self.model is not None
        for name, param in self.model.policy.named_parameters():
            if not torch.isfinite(param).all():
                raise RuntimeError(f"Paramètre non fini détecté: {name}")


class EvalSelectCallback(BaseCallback):
    """
    Evalue périodiquement le modèle, sauvegarde le meilleur et déclenche
    un early-stop si le winrate ne s'améliore plus.
    """

    def __init__(
        self,
        eval_freq_steps,
        n_eval_games,
        models_dir,
        best_name_prefix,
        no_improve_patience,
        eval_env_kwargs=None,
    ):
        super().__init__()
        self.eval_freq_steps = eval_freq_steps
        self.n_eval_games = n_eval_games
        self.models_dir = models_dir
        self.best_name_prefix = best_name_prefix
        self.no_improve_patience = no_improve_patience

        self.eval_env = RiskGymEnv(**(eval_env_kwargs or {}))
        self.last_eval_step = 0
        self.best_score = -1.0
        self.no_improve_count = 0
        self.stop_now = False

    def _on_step(self):
        return not self.stop_now

    def _evaluate(self):
        assert self.model is not None
        wins = 0
        rewards = []
        lengths = []

        seeds = [50_000 + i for i in range(self.n_eval_games)]
        for seed in seeds:
            random.seed(seed)
            np.random.seed(seed)
            obs, _ = self.eval_env.reset(seed=seed)
            done = False
            ep_reward = 0.0
            ep_len = 0

            while not done:
                action_masks = get_action_masks(self.eval_env)
                action, _ = self.model.predict(obs, action_masks=action_masks, deterministic=True)
                obs, reward, terminated, truncated, _ = self.eval_env.step(action)
                ep_reward += float(reward)
                ep_len += 1
                done = terminated or truncated

            if self.eval_env.engine.players[0].is_alive:
                wins += 1
            rewards.append(ep_reward)
            lengths.append(ep_len)

        winrate = wins / self.n_eval_games
        lower_ci = self._wilson_lower_bound(wins, self.n_eval_games)
        return winrate, lower_ci, float(np.mean(rewards)), float(np.mean(lengths))

    @staticmethod
    def _wilson_lower_bound(wins, n, z=1.96):
        if n <= 0:
            return 0.0
        p = wins / n
        denom = 1.0 + (z * z) / n
        center = p + (z * z) / (2.0 * n)
        radius = z * math.sqrt((p * (1.0 - p) + (z * z) / (4.0 * n)) / n)
        return (center - radius) / denom

    def _on_rollout_end(self):
        if self.num_timesteps - self.last_eval_step < self.eval_freq_steps:
            return

        self.last_eval_step = self.num_timesteps
        winrate, score, avg_reward, avg_len = self._evaluate()
        print(
            f"[EVAL] steps={self.num_timesteps} "
            f"winrate={winrate:.3f} score={score:.3f} "
            f"reward={avg_reward:.2f} len={avg_len:.1f}"
        )

        # Sélection plus robuste: borne basse CI95 du winrate.
        if score > self.best_score:
            self.best_score = score
            self.no_improve_count = 0
            best_path = f"{self.models_dir}/{self.best_name_prefix}"
            assert self.model is not None
            self.model.save(best_path)
            #print(f"[EVAL] Nouveau meilleur modèle sauvegardé: {best_path}.zip")
        else:
            self.no_improve_count += 1
            print(
                f"[EVAL] Pas d'amélioration "
                f"({self.no_improve_count}/{self.no_improve_patience})"
            )
            if self.no_improve_count >= self.no_improve_patience:
                #print("[EVAL] Early-stop: stagnation détectée.")
                self.stop_now = True

    def _on_training_end(self):
        self.eval_env.close()


class SelfPlaySnapshotCallback(BaseCallback):
    """Sauvegarde périodiquement un snapshot fixe pour l'adversaire self-play."""

    def __init__(self, save_freq_steps, snapshot_path):
        super().__init__()
        self.save_freq_steps = save_freq_steps
        self.snapshot_path = snapshot_path
        self.last_save_step = 0

    def _on_step(self):
        return True

    def _on_rollout_end(self):
        if self.num_timesteps - self.last_save_step < self.save_freq_steps:
            return
        self.last_save_step = self.num_timesteps
        assert self.model is not None
        self.model.save(self.snapshot_path)


class OpponentCurriculumCallback(BaseCallback):
    """Fait évoluer le pool d'adversaires par phases durant le run courant."""

    def __init__(self, phase_a_steps=10_000_000, phase_b_steps=25_000_000):
        super().__init__()
        self.phase_a_steps = phase_a_steps
        self.phase_b_steps = phase_b_steps
        self.base_timesteps = 0
        self.current_phase = None

    def _on_training_start(self):
        assert self.model is not None
        self.base_timesteps = int(self.model.num_timesteps)
        self._apply_phase(force=True)

    def _on_step(self):
        self._apply_phase(force=False)
        return True

    def _unwrap_risk_env(self):
        assert self.model is not None
        env = self.model.get_env()
        if hasattr(env, "envs") and len(env.envs) > 0:
            env = env.envs[0]
        while hasattr(env, "env"):
            env = env.env
        return env

    def _target_pool(self, phase_name):
        if phase_name == "A":
            return {
                "naive": 0.45,
                "aggressive": 0.25,
                "random": 0.25,
                "selfplay": 0.05,
            }
        if phase_name == "B":
            return {
                "naive": 0.35,
                "aggressive": 0.25,
                "random": 0.25,
                "selfplay": 0.15,
            }
        return {
            "naive": 0.35,
            "aggressive": 0.20,
            "random": 0.20,
            "selfplay": 0.25,
        }

    def _apply_phase(self, force=False):
        run_steps = int(self.num_timesteps - self.base_timesteps)
        if run_steps < self.phase_a_steps:
            phase = "A"
        elif run_steps < self.phase_b_steps:
            phase = "B"
        else:
            phase = "C"

        if not force and phase == self.current_phase:
            return

        self.current_phase = phase
        env = self._unwrap_risk_env()
        new_pool = self._target_pool(phase)
        env.opponent_pool = new_pool
        print(f"[CURRICULUM] phase={phase} run_steps={run_steps} pool={new_pool}")


def apply_finetune_hparams(model):
    """Hyperparamètres de fine-tuning pour éviter la dérive observée après 20M."""
    lr = 5e-5
    model.learning_rate = lr
    model.lr_schedule = get_schedule_fn(lr)
    model.ent_coef = 0.01
    model.target_kl = 0.02


def train(former_model_name=None):
    # Workaround: sur torch 2.8, le check Simplex() peut échouer sporadiquement
    # avec action masking à cause d'un écart numérique très faible.
    Distribution.set_default_validate_args(False)

    models_dir = "risk_game/models/PPO"
    log_dir = "risk_game/logs"
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    selfplay_snapshot = f"{models_dir}/risk_v11_selfplay_latest"
    selfplay_models = [
        f"{models_dir}/risk_v11_best",
        f"{models_dir}/risk_v11_94M_94014338_steps",
        f"{models_dir}/risk_v11_84M_84013954_steps",
        f"{models_dir}/risk_v10_champion",
        f"{models_dir}/risk_v10_ckpt_76008321_steps",
        selfplay_snapshot,
    ]

    #print("Initialisation de l'environnement...")
    env = RiskGymEnv(
        opponent_mode="pool",
        opponent_pool={
            "naive": 0.45,
            "aggressive": 0.25,
            "random": 0.25,
            "selfplay": 0.05,
        },
        selfplay_models=selfplay_models,
        selfplay_deterministic=False,
    )
    env = ActionMasker(env, mask_fn)

    model_path = f"{models_dir}/{former_model_name}.zip" if former_model_name else ""
    is_resume = bool(former_model_name and os.path.exists(model_path))

    if is_resume:
        #print(f"Reprise de l'entraînement à partir du modèle : {model_path}...")
        model = MaskablePPO.load(model_path, env=env, tensorboard_log=log_dir)
    else:
        #print("Création d'un nouveau modèle MaskablePPO...")
        model = MaskablePPO(
            "MlpPolicy",
            env,
            learning_rate=5e-5,
            ent_coef=0.01,
            target_kl=0.02,
            verbose=1,
            tensorboard_log=log_dir,
        )

    apply_finetune_hparams(model)

    timesteps = 25_000_000
    #print(f"Lancement de l'entraînement pour {timesteps} pas...")

    callbacks = CallbackList(
        [
            CheckpointCallback(
                save_freq=2_000_000,
                save_path=models_dir,
                name_prefix="risk_v11_ckpt",
                save_replay_buffer=False,
                save_vecnormalize=False,
            ),
            SelfPlaySnapshotCallback(
                save_freq_steps=1_000_000,
                snapshot_path=selfplay_snapshot,
            ),
            OpponentCurriculumCallback(
                phase_a_steps=10_000_000,
                phase_b_steps=25_000_000,
            ),
            FinitePolicyCallback(),
            EvalSelectCallback(
                eval_freq_steps=2_000_000,
                n_eval_games=300,
                models_dir=models_dir,
                best_name_prefix="risk_v11_best",
                no_improve_patience=4,
                eval_env_kwargs={"opponent_mode": "naive"},
            ),
        ]
    )

    try:
        model.learn(
            total_timesteps=timesteps,
            progress_bar=True,
            callback=callbacks,
            reset_num_timesteps=not is_resume,
        )
    except Exception:
        crash_name = f"risk_v11_crash_{int(time.time())}"
        crash_path = f"{models_dir}/{crash_name}"
        model.save(crash_path)
        #print(f"Crash détecté: modèle sauvegardé dans {crash_path}.zip")
        raise

    final_steps = int(model.num_timesteps)
    model.save(f"{models_dir}/risk_v11_{final_steps // 1_000_000}M_{final_steps}_steps")
    #print(f"Entraînement terminé et modèle sauvegardé ({final_steps} steps) !")


if __name__ == "__main__":
    # Recommandé: reprendre depuis le meilleur checkpoint observé.
    train("risk_v11_best")
