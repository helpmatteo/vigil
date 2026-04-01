from __future__ import annotations

import pytest

from vigil.config import DEFAULT_METRIC_PATTERNS, Config
from vigil.presets import PRESETS, apply_preset, detect_framework


# ---------------------------------------------------------------------------
# detect_framework
# ---------------------------------------------------------------------------


class TestDetectFramework:
    def test_detects_huggingface(self):
        lines = ["from transformers import Trainer", "model = AutoModel.from_pretrained('bert')"]
        assert detect_framework(lines) == "huggingface"

    def test_detects_lightning(self):
        lines = ["import pytorch_lightning as pl", "trainer = pl.Trainer(max_epochs=10)"]
        assert detect_framework(lines) == "lightning"

    def test_detects_dreamer(self):
        lines = ["Loading DreamerV3 agent", "rssm loss: 0.42"]
        assert detect_framework(lines) == "dreamer"

    def test_returns_none_for_unrelated_lines(self):
        lines = ["Hello world", "Running some random script", "Done."]
        assert detect_framework(lines) is None

    def test_returns_none_for_empty_list(self):
        assert detect_framework([]) is None

    def test_case_insensitive(self):
        lines = ["TRANSFORMERS trainer loaded"]
        assert detect_framework(lines) == "huggingface"

    def test_picks_best_match_with_most_keywords(self):
        lines = [
            "import transformers",
            "from transformers import Trainer",
            "huggingface hub connected",
            "import pytorch_lightning",  # only 1 keyword for lightning
        ]
        assert detect_framework(lines) == "huggingface"

    def test_single_keyword_sufficient(self):
        lines = ["dreamer agent started"]
        assert detect_framework(lines) == "dreamer"

    def test_all_presets_detectable(self):
        for key, preset in PRESETS.items():
            lines = [kw for kw in preset["detect_keywords"]]
            assert detect_framework(lines) == key, f"Failed to detect preset {key!r}"

    def test_tie_breaks_by_iteration_order(self):
        # Each preset gets exactly 1 keyword hit — first one in dict order wins.
        lines = ["transformers", "lightning", "dreamer"]
        result = detect_framework(lines)
        # With 1 hit each, first preset iterated with count=1 wins. Because PRESETS
        # is ordered, "huggingface" is first and gets count=1, then "lightning" ties
        # but doesn't beat (strictly >), so huggingface wins.
        assert result == "huggingface"


# ---------------------------------------------------------------------------
# apply_preset
# ---------------------------------------------------------------------------


class TestApplyPreset:
    def _make_config(self, **overrides) -> Config:
        return Config(**overrides)

    def test_applies_huggingface_patterns(self):
        cfg = self._make_config()
        apply_preset(cfg, "huggingface")
        hf_extras = PRESETS["huggingface"]["extra_metric_patterns"]
        for pat in hf_extras:
            assert pat in cfg.extra_metric_patterns
            assert pat in cfg.metric_patterns

    def test_metric_patterns_equals_default_plus_extras(self):
        cfg = self._make_config()
        apply_preset(cfg, "lightning")
        expected = DEFAULT_METRIC_PATTERNS.copy() + cfg.extra_metric_patterns
        assert cfg.metric_patterns == expected

    def test_merges_decrease_good_with_existing(self):
        cfg = self._make_config(decrease_good={"my_custom_loss"})
        apply_preset(cfg, "huggingface")
        assert "my_custom_loss" in cfg.decrease_good
        for m in PRESETS["huggingface"]["decrease_good"]:
            assert m in cfg.decrease_good

    def test_merges_increase_good_with_existing(self):
        cfg = self._make_config(increase_good={"my_metric"})
        apply_preset(cfg, "dreamer")
        assert "my_metric" in cfg.increase_good
        for m in PRESETS["dreamer"]["increase_good"]:
            assert m in cfg.increase_good

    def test_merges_counters_with_existing(self):
        cfg = self._make_config(counters={"iteration"})
        apply_preset(cfg, "dreamer")
        assert "iteration" in cfg.counters
        assert "episode" in cfg.counters

    def test_preserves_user_extra_metric_patterns(self):
        user_pattern = r"custom_metric[:\s=]+(?P<custom>[\d.]+)"
        cfg = self._make_config(extra_metric_patterns=[user_pattern])
        apply_preset(cfg, "huggingface")
        assert user_pattern in cfg.extra_metric_patterns
        assert user_pattern in cfg.metric_patterns

    def test_no_duplicate_preset_patterns(self):
        cfg = self._make_config()
        apply_preset(cfg, "lightning")
        # Apply same preset twice — preset patterns should not duplicate.
        apply_preset(cfg, "lightning")
        lt_extras = PRESETS["lightning"]["extra_metric_patterns"]
        for pat in lt_extras:
            assert cfg.extra_metric_patterns.count(pat) == 1

    def test_noop_for_unknown_preset(self):
        cfg = self._make_config()
        original_patterns = cfg.metric_patterns.copy()
        original_decrease = cfg.decrease_good.copy()
        apply_preset(cfg, "nonexistent_preset")
        assert cfg.metric_patterns == original_patterns
        assert cfg.decrease_good == original_decrease

    def test_plateau_metrics_set_from_preset(self):
        cfg = self._make_config()
        apply_preset(cfg, "dreamer")
        assert cfg.plateau_metrics == PRESETS["dreamer"]["plateau_metrics"]

    def test_all_presets_apply_without_error(self):
        for key in PRESETS:
            cfg = self._make_config()
            apply_preset(cfg, key)
            assert len(cfg.extra_metric_patterns) > 0


# ---------------------------------------------------------------------------
# PRESETS structure validation
# ---------------------------------------------------------------------------


class TestPresetsStructure:
    @pytest.mark.parametrize("key", list(PRESETS.keys()))
    def test_required_keys_present(self, key: str):
        preset = PRESETS[key]
        required = {
            "label",
            "description",
            "detect_keywords",
            "extra_metric_patterns",
            "decrease_good",
            "increase_good",
            "counters",
            "plateau_metrics",
        }
        assert required.issubset(preset.keys()), f"Preset {key!r} missing keys: {required - preset.keys()}"

    @pytest.mark.parametrize("key", list(PRESETS.keys()))
    def test_detect_keywords_nonempty(self, key: str):
        assert len(PRESETS[key]["detect_keywords"]) > 0

    @pytest.mark.parametrize("key", list(PRESETS.keys()))
    def test_extra_metric_patterns_are_strings(self, key: str):
        for pat in PRESETS[key]["extra_metric_patterns"]:
            assert isinstance(pat, str)
