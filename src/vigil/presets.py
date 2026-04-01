from __future__ import annotations

from typing import Any

PRESETS: dict[str, dict[str, Any]] = {
    "huggingface": {
        "label": "HuggingFace Trainer",
        "description": "Transformers Trainer with eval metrics",
        "detect_keywords": ["transformers", "Trainer", "huggingface"],
        "extra_metric_patterns": [
            "'?eval_loss'?[:\\s=]+(?P<eval_loss>[\\d.]+)",
            "'?train_loss'?[:\\s=]+(?P<train_loss>[\\d.]+)",
            "'?learning_rate'?[:\\s=]+(?P<learning_rate>[\\d.e\\-]+)",
            "'?eval_accuracy'?[:\\s=]+(?P<eval_accuracy>[\\d.]+)",
            "'?grad_norm'?[:\\s=]+(?P<grad_norm>[\\d.]+)",
            "'?train_samples_per_second'?[:\\s=]+(?P<samples_sec>[\\d.]+)",
        ],
        "decrease_good": {"loss", "eval_loss", "train_loss", "grad_norm", "rssm", "vc", "tom"},
        "increase_good": {"reward", "accuracy", "eval_accuracy", "samples_sec"},
        "counters": {"step", "epoch"},
        "plateau_metrics": ["loss", "eval_loss"],
    },
    "lightning": {
        "label": "PyTorch Lightning",
        "description": "Lightning Trainer with validation metrics",
        "detect_keywords": ["pytorch_lightning", "pl.Trainer", "lightning"],
        "extra_metric_patterns": [
            "val_loss[:\\s=]+(?P<val_loss>[\\d.]+)",
            "train_loss[:\\s=]+(?P<train_loss>[\\d.]+)",
            "val_acc[:\\s=]+(?P<val_acc>[\\d.]+)",
            "train_acc[:\\s=]+(?P<train_acc>[\\d.]+)",
        ],
        "decrease_good": {"loss", "val_loss", "train_loss", "rssm", "vc", "tom"},
        "increase_good": {"reward", "accuracy", "val_acc", "train_acc"},
        "counters": {"step", "epoch"},
        "plateau_metrics": ["loss", "val_loss"],
    },
    "dreamer": {
        "label": "Dreamer / RL",
        "description": "DreamerV3 and reinforcement learning",
        "detect_keywords": ["dreamer", "rssm", "DreamerV3"],
        "extra_metric_patterns": [
            "ep_return[:\\s=]+(?P<ep_return>[\\d.\\-e]+)",
            "episode[:\\s=]+(?P<episode>[\\d]+)",
            "fps[:\\s=]+(?P<fps>[\\d.]+)",
            "policy_loss[:\\s=]+(?P<policy_loss>[\\d.\\-e]+)",
            "value_loss[:\\s=]+(?P<value_loss>[\\d.\\-e]+)",
            "model_loss[:\\s=]+(?P<model_loss>[\\d.\\-e]+)",
        ],
        "decrease_good": {"loss", "rssm", "vc", "tom", "actor", "policy_loss", "value_loss", "model_loss"},
        "increase_good": {"reward", "ep_return", "accuracy", "fps"},
        "counters": {"step", "epoch", "episode"},
        "plateau_metrics": ["loss", "reward"],
    },
}


def detect_framework(log_lines: list[str]) -> str | None:
    """Scan log lines and return the best-matching preset key, or None."""
    text = "\n".join(log_lines).lower()
    best_key: str | None = None
    best_count = 0
    for key, preset in PRESETS.items():
        count = sum(1 for kw in preset["detect_keywords"] if kw.lower() in text)
        if count > best_count:
            best_count = count
            best_key = key
    return best_key if best_count > 0 else None


def apply_preset(config: object, preset_key: str) -> None:
    """Apply a preset's fields onto a Config object.

    Rebuilds metric_patterns from DEFAULT + extra to avoid double-append.
    """
    from .config import DEFAULT_METRIC_PATTERNS

    preset = PRESETS.get(preset_key)
    if not preset:
        return

    preset_extras = list(preset["extra_metric_patterns"])
    user_extras = [p for p in config.extra_metric_patterns if p not in preset_extras]
    config.extra_metric_patterns = preset_extras + user_extras
    config.metric_patterns = DEFAULT_METRIC_PATTERNS.copy() + config.extra_metric_patterns
    config.decrease_good = set(preset["decrease_good"]) | config.decrease_good
    config.increase_good = set(preset["increase_good"]) | config.increase_good
    config.counters = set(preset["counters"]) | config.counters
    config.plateau_metrics = list(preset["plateau_metrics"])
