"""Tests for mapfile.py — JSON serialisation and migration."""

import json
import os
import tempfile

import pytest

from ghostengine.mapfile import _migrate, build_colors, build_entities, load_raw, save_raw
from ghostengine.frame import EntityView


class TestMigrate:
    def test_no_version_becomes_v1(self) -> None:
        data = {"grid": [[0, 1], [1, 0]]}
        result = _migrate(data)
        assert result["version"] == 3

    def test_already_v1_passes_through(self) -> None:
        data = {"version": 1, "grid": [[0]]}
        result = _migrate(data)
        assert result is data  # same object returned

    def test_preserves_other_keys(self) -> None:
        data = {"grid": [[1]], "entities": [], "colors": {}}
        result = _migrate(data)
        assert result["grid"] == [[1]]
        assert result["entities"] == []
        assert result["colors"] == {}

    def test_exit_migrates_to_portal_entity(self) -> None:
        data = {"grid": [[0]], "exit": {"x": 3, "y": 7, "target_map": "other.json"}}
        result = _migrate(data)
        assert result["version"] == 3
        assert "exit" not in result
        entities = result.get("entities", [])
        assert len(entities) == 1
        portal = entities[0]
        assert portal["kind"] == "portal"
        assert portal["x"] == 3.5
        assert portal["y"] == 7.5
        # v2→v3 converts coordinate targets to null
        assert portal["portal_target"] is None


class TestSaveLoadRaw:
    def test_round_trip(self) -> None:
        data = {"version": 1, "grid": [[0, 1], [1, 0]], "entities": []}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8",
        ) as f:
            path = f.name

        try:
            save_raw(data, path)
            loaded = load_raw(path)
            assert loaded["version"] == 3
            assert loaded["grid"] == [[0, 1], [1, 0]]
        finally:
            os.unlink(path)


class TestBuildColors:
    def test_defaults_when_empty(self) -> None:
        config = build_colors({}, None)
        assert config.sky_top == (135, 206, 235)
        assert config.sky_bottom == (240, 248, 255)
        assert config.floor == (34, 139, 34)
        assert config.walls == {}

    def test_custom_colors(self) -> None:
        raw = {
            "colors": {
                "sky_top": [10, 20, 30],
                "sky_bottom": [40, 50, 60],
                "floor": [70, 80, 90],
                "walls": {
                    "1": {"color": [200, 100, 50]},
                    "2": {"color": [50, 200, 100]},
                },
            },
        }
        config = build_colors(raw, None)
        assert config.sky_top == (10, 20, 30)
        assert config.walls[1].color == (200, 100, 50)
        assert config.walls[2].color == (50, 200, 100)
        # texture is None when no loader
        assert config.walls[1].texture is None

    def test_missing_walls_section(self) -> None:
        raw = {"colors": {"sky_top": [0, 0, 0]}}
        config = build_colors(raw, None)
        assert config.walls == {}


class TestBuildEntities:
    def test_empty_list(self) -> None:
        ents = build_entities({"entities": []}, None)
        assert ents == []

    def test_minimal_entity(self) -> None:
        raw = {"entities": [{"x": 3.5, "y": 4.5, "texture": ""}]}
        ents = build_entities(raw, None)
        assert len(ents) == 1
        e = ents[0]
        assert e.x == 3.5
        assert e.y == 4.5
        assert e.texture is None  # no texture loader, empty path
        assert e.size_3d == 150  # default
        assert e.occlusion == "center"  # default

    def test_full_entity(self) -> None:
        raw = {
            "entities": [
                {
                    "x": 1.5, "y": 2.5,
                    "texture": "ghost.png",
                    "size_3d": 800, "width_3d": 0.8,
                    "anim": {"float": {"speed": 0.003, "amp": 0.05}},
                    "occlusion": "per_column",
                },
            ],
        }
        ents = build_entities(raw, None)
        assert len(ents) == 1
        e = ents[0]
        assert e.size_3d == 800
        assert e.width_3d == 0.8
        assert e.occlusion == "per_column"
        assert e.anim == {"float": {"speed": 0.003, "amp": 0.05}}
        # texture is None since no loader resolves the path
