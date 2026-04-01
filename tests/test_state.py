from __future__ import annotations

import json

from vigil.state import AppState, load_state


# ---------------------------------------------------------------------------
# AppState.is_hint_completed
# ---------------------------------------------------------------------------


class TestIsHintCompleted:
    def test_returns_false_for_empty_state(self):
        state = AppState()
        assert state.is_hint_completed("any_hint") is False

    def test_returns_true_after_adding_hint(self):
        state = AppState(hints_completed=["hint_a"])
        assert state.is_hint_completed("hint_a") is True

    def test_returns_false_for_different_hint(self):
        state = AppState(hints_completed=["hint_a"])
        assert state.is_hint_completed("hint_b") is False


# ---------------------------------------------------------------------------
# AppState.complete_hint
# ---------------------------------------------------------------------------


class TestCompleteHint:
    def test_adds_hint(self, tmp_path):
        state = AppState(_state_path=tmp_path / "state.json")
        state.complete_hint("first")
        assert "first" in state.hints_completed

    def test_no_duplicate_on_second_call(self, tmp_path):
        state = AppState(_state_path=tmp_path / "state.json")
        state.complete_hint("dup")
        state.complete_hint("dup")
        assert state.hints_completed.count("dup") == 1

    def test_persists_to_disk(self, tmp_path):
        path = tmp_path / "state.json"
        state = AppState(_state_path=path)
        state.complete_hint("persisted")
        assert path.exists()
        data = json.loads(path.read_text())
        assert "persisted" in data["hints_completed"]

    def test_multiple_hints_preserved(self, tmp_path):
        state = AppState(_state_path=tmp_path / "state.json")
        state.complete_hint("a")
        state.complete_hint("b")
        state.complete_hint("c")
        assert state.hints_completed == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# AppState.save + load_state round trip
# ---------------------------------------------------------------------------


class TestSaveLoadRoundTrip:
    def test_round_trip(self, tmp_path):
        path = tmp_path / "state.json"
        state = AppState(hints_completed=["x", "y", "z"], _state_path=path)
        state.save()
        loaded = load_state(path)
        assert loaded.hints_completed == ["x", "y", "z"]

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "nested" / "deep" / "state.json"
        state = AppState(hints_completed=["nested"], _state_path=path)
        state.save()
        assert path.exists()
        loaded = load_state(path)
        assert loaded.hints_completed == ["nested"]

    def test_save_to_explicit_path(self, tmp_path):
        default_path = tmp_path / "default.json"
        explicit_path = tmp_path / "explicit.json"
        state = AppState(hints_completed=["alt"], _state_path=default_path)
        state.save(path=explicit_path)
        assert explicit_path.exists()
        assert not default_path.exists()

    def test_empty_state_round_trip(self, tmp_path):
        path = tmp_path / "state.json"
        state = AppState(_state_path=path)
        state.save()
        loaded = load_state(path)
        assert loaded.hints_completed == []

    def test_atomic_write_no_leftover_tmp(self, tmp_path):
        path = tmp_path / "state.json"
        state = AppState(hints_completed=["clean"], _state_path=path)
        state.save()
        tmp_files = list(tmp_path.glob(".state_*.tmp"))
        assert tmp_files == []


# ---------------------------------------------------------------------------
# load_state edge cases
# ---------------------------------------------------------------------------


class TestLoadState:
    def test_missing_file_returns_fresh_state(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        state = load_state(path)
        assert state.hints_completed == []
        assert state._state_path == path

    def test_corrupted_json_returns_fresh_state(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text("{not valid json!!")
        state = load_state(path)
        assert state.hints_completed == []

    def test_json_missing_hints_key_returns_fresh(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text(json.dumps({"other_key": 42}))
        state = load_state(path)
        assert state.hints_completed == []

    def test_json_hints_wrong_type_returns_fresh(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text(json.dumps({"hints_completed": "not_a_list"}))
        state = load_state(path)
        assert state.hints_completed == []

    def test_valid_file_loads_hints(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text(json.dumps({"hints_completed": ["a", "b"]}))
        state = load_state(path)
        assert state.hints_completed == ["a", "b"]

    def test_state_path_set_on_loaded_state(self, tmp_path):
        path = tmp_path / "state.json"
        state = load_state(path)
        assert state._state_path == path


# ---------------------------------------------------------------------------
# AppState.reset
# ---------------------------------------------------------------------------


class TestReset:
    def test_clears_hints(self, tmp_path):
        state = AppState(hints_completed=["a", "b"], _state_path=tmp_path / "state.json")
        state.reset()
        assert state.hints_completed == []

    def test_deletes_state_file(self, tmp_path):
        path = tmp_path / "state.json"
        state = AppState(hints_completed=["a"], _state_path=path)
        state.save()
        assert path.exists()
        state.reset()
        assert not path.exists()

    def test_reset_tolerates_missing_file(self, tmp_path):
        path = tmp_path / "does_not_exist.json"
        state = AppState(_state_path=path)
        state.reset()
        assert state.hints_completed == []

    def test_reset_then_save_round_trip(self, tmp_path):
        path = tmp_path / "state.json"
        state = AppState(hints_completed=["old"], _state_path=path)
        state.save()
        state.reset()
        state.complete_hint("new")
        loaded = load_state(path)
        assert loaded.hints_completed == ["new"]
