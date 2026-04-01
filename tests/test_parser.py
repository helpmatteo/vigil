from vigil.parser import MetricParser, MetricState
from vigil.config import DEFAULT_METRIC_PATTERNS


def test_parse_loss():
    parser = MetricParser(DEFAULT_METRIC_PATTERNS)
    result = parser.parse_line("Step 100: loss=0.0234")
    assert result["loss"] == "0.0234"
    assert parser.parse_line("loss: 1.234") == {"loss": "1.234"}
    assert parser.parse_line("train loss = 0.5") == {"loss": "0.5"}


def test_parse_step():
    parser = MetricParser(DEFAULT_METRIC_PATTERNS)
    assert parser.parse_line("step: 1500")["step"] == "1500"
    assert parser.parse_line("Step=2,000")["step"] == "2,000"


def test_parse_epoch():
    parser = MetricParser(DEFAULT_METRIC_PATTERNS)
    assert parser.parse_line("epoch: 3/10")["epoch"] == "3/10"
    assert parser.parse_line("Epoch 5")["epoch"] == "5"


def test_parse_lr():
    parser = MetricParser(DEFAULT_METRIC_PATTERNS)
    assert parser.parse_line("lr=1e-4")["lr"] == "1e-4"
    assert parser.parse_line("learning rate lr: 3.5e-05")["lr"] == "3.5e-05"


def test_parse_reward():
    parser = MetricParser(DEFAULT_METRIC_PATTERNS)
    assert parser.parse_line("reward: 12.5")["reward"] == "12.5"
    assert parser.parse_line("reward=-0.5")["reward"] == "-0.5"


def test_parse_dreamer_metrics():
    parser = MetricParser(DEFAULT_METRIC_PATTERNS)
    line = "Step   3500/25000 (14%) | rssm=1.0008 | vc=0.0009 | tom=1.1943 | actor=-0.0018"
    result = parser.parse_line(line)
    assert result["step"] == "3500"
    assert result["rssm"] == "1.0008"
    assert result["vc"] == "0.0009"
    assert result["tom"] == "1.1943"
    assert result["actor"] == "-0.0018"


def test_parse_multiple_metrics():
    parser = MetricParser(DEFAULT_METRIC_PATTERNS)
    result = parser.parse_line("step: 100, loss: 0.05, lr: 1e-4")
    assert result["step"] == "100"
    assert result["loss"] == "0.05"
    assert result["lr"] == "1e-4"


def test_parse_no_metrics():
    parser = MetricParser(DEFAULT_METRIC_PATTERNS)
    assert parser.parse_line("Loading model from checkpoint...") == {}


def test_metric_state_direction():
    state = MetricState()
    state.update({"loss": "1.0"})
    assert state.direction("loss") == "neutral"  # no previous

    state.update({"loss": "0.5"})
    assert state.direction("loss") == "down"

    state.update({"loss": "0.8"})
    assert state.direction("loss") == "up"


def test_metric_state_tracks_multiple():
    state = MetricState()
    state.update({"loss": "1.0", "step": "100"})
    state.update({"loss": "0.5", "step": "200"})
    assert state.current == {"loss": "0.5", "step": "200"}
    assert state.previous == {"loss": "1.0", "step": "100"}


def test_sparkline():
    state = MetricState()
    # Need at least 2 values for sparkline
    state.update({"loss": "1.0"})
    assert state.sparkline("loss") == ""  # only 1 value

    for v in ["0.8", "0.6", "0.4", "0.2"]:
        state.update({"loss": v})
    spark = state.sparkline("loss")
    assert len(spark) == 5  # 5 values total
    assert spark[0] > spark[-1]  # decreasing values = higher blocks first


def test_sparkline_flat():
    state = MetricState()
    for _ in range(5):
        state.update({"loss": "1.0"})
    spark = state.sparkline("loss")
    assert len(set(spark)) == 1  # all same character


def test_nan_detection():
    state = MetricState()
    state.update({"loss": "0.5"})
    assert state.has_nan() is None

    state.update({"loss": "nan"})
    assert state.has_nan() == "loss"


def test_inf_detection():
    state = MetricState()
    state.update({"loss": "inf"})
    assert state.has_nan() == "loss"


def test_history_max_length():
    state = MetricState()
    for i in range(100):
        state.update({"loss": str(float(i))})
    assert len(state.history["loss"]) == state.MAX_HISTORY


def test_parse_line_prefilter():
    parser = MetricParser(DEFAULT_METRIC_PATTERNS)
    result = parser.parse_line("INFO: downloading weights from hub...")
    assert result == {}
    result = parser.parse_line("Compiling CUDA kernels, please wait")
    assert result == {}


def test_invalid_regex_pattern():
    patterns = [r"loss[:\s=]+(?P<loss>[\d.]+)", r"(?P<bad>[unclosed"]
    parser = MetricParser(patterns)
    assert len(parser.warnings) == 1
    assert "Skipping invalid pattern" in parser.warnings[0]
    assert len(parser.patterns) == 1
    assert parser.parse_line("loss: 0.5") == {"loss": "0.5"}


def test_metric_state_configurable_history():
    state = MetricState(max_history=5)
    assert state.MAX_HISTORY == 5
    for i in range(20):
        state.update({"loss": str(float(i))})
    assert len(state.history["loss"]) == 5
    assert list(state.history["loss"]) == [15.0, 16.0, 17.0, 18.0, 19.0]


def test_plateau_detection():
    state = MetricState()
    for _ in range(10):
        state.update({"loss": "0.5"})
    assert state.has_plateau("loss", window=8) is True

    state_varying = MetricState()
    for i in range(10):
        state_varying.update({"loss": str(float(i))})
    assert state_varying.has_plateau("loss", window=8) is False


def test_plateau_insufficient_data():
    state = MetricState()
    for _ in range(3):
        state.update({"loss": "0.5"})
    assert state.has_plateau("loss", window=8) is False
    assert state.has_plateau("nonexistent", window=8) is False


def test_metric_state_reset():
    state = MetricState()
    state.update({"loss": "1.0", "step": "100"})
    state.update({"loss": "0.5", "step": "200"})
    assert len(state.current) == 2
    assert len(state.previous) == 2
    assert len(state.history) == 2

    state.reset()
    assert state.current == {}
    assert state.previous == {}
    assert state.history == {}


def test_keywords_extracted():
    parser = MetricParser(DEFAULT_METRIC_PATTERNS)
    expected_keys = {"loss", "step", "epoch", "lr", "reward", "accuracy",
                     "rssm", "vc", "tom", "actor"}
    assert expected_keys.issubset(parser._keywords)


# ------------------------------------------------------------------
# Edge case coverage for ValueError branches
# ------------------------------------------------------------------


def test_metric_state_update_non_numeric():
    """update with non-numeric value stores in current but does NOT add to history (lines 35-36)."""
    state = MetricState()
    state.update({"loss": "N/A"})
    assert state.current["loss"] == "N/A"
    assert "loss" in state.history
    assert len(state.history["loss"]) == 0  # float("N/A") fails, no append


def test_metric_state_update_mixed_numeric_non_numeric():
    """Numeric values go to history, non-numeric ones do not."""
    state = MetricState()
    state.update({"loss": "0.5", "status": "running"})
    assert len(state.history["loss"]) == 1
    assert len(state.history["status"]) == 0
    assert state.current["status"] == "running"


def test_metric_state_direction_non_numeric():
    """direction with non-numeric previous/current returns 'neutral' (lines 48-50)."""
    state = MetricState()
    state.update({"loss": "good"})
    state.update({"loss": "bad"})
    assert state.direction("loss") == "neutral"


def test_metric_state_direction_previous_non_numeric():
    """direction when only previous is non-numeric returns 'neutral'."""
    state = MetricState()
    state.update({"loss": "N/A"})
    state.update({"loss": "0.5"})
    assert state.direction("loss") == "neutral"


def test_metric_state_has_nan_non_numeric():
    """has_nan with non-numeric value skips without error (lines 71-72)."""
    state = MetricState()
    state.update({"loss": "not-a-number"})
    # Should not crash and should return None (non-numeric is not NaN)
    assert state.has_nan() is None


def test_metric_state_has_nan_mixed():
    """has_nan skips non-numeric values and finds actual NaN."""
    state = MetricState()
    state.update({"status": "running", "loss": "nan"})
    result = state.has_nan()
    # "status" is non-numeric (skipped), "loss" is NaN
    assert result == "loss"


def test_keyword_prefilter_no_keywords():
    """Line with no metric keywords returns empty dict early (line 116)."""
    parser = MetricParser(DEFAULT_METRIC_PATTERNS)
    result = parser.parse_line("Successfully loaded the checkpoint from disk.")
    assert result == {}


def test_keyword_prefilter_various_non_matching():
    """Various lines with no keywords all return empty via pre-filter."""
    parser = MetricParser(DEFAULT_METRIC_PATTERNS)
    assert parser.parse_line("Downloading https://example.com/model.bin") == {}
    assert parser.parse_line("GPU memory: 24576 MiB") == {}
    assert parser.parse_line("") == {}
