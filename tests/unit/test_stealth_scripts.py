"""
tests/unit/test_stealth_scripts.py — Validate stealth JS files exist and contain expected markers.
"""

from __future__ import annotations

import os

import pytest

STEALTH_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "workers", "stealth")

EXPECTED_FILES = [
    "canvas_fingerprint.js",
    "chrome_runtime.js",
    "keyboard_timing.js",
    "mouse_movement.js",
    "navigator.js",
    "timezone.js",
    "webgl_override.js",
]


def _read_stealth(filename: str) -> str:
    path = os.path.join(STEALTH_DIR, filename)
    with open(path) as f:
        return f.read()


class TestStealthFilesExist:
    @pytest.mark.parametrize("filename", EXPECTED_FILES)
    def test_file_exists(self, filename):
        path = os.path.join(STEALTH_DIR, filename)
        assert os.path.isfile(path), f"Missing stealth file: {filename}"

    def test_all_seven_files_present(self):
        actual = sorted(f for f in os.listdir(STEALTH_DIR) if f.endswith(".js"))
        assert actual == sorted(EXPECTED_FILES)


class TestStealthFileContents:
    def test_navigator_removes_webdriver(self):
        content = _read_stealth("navigator.js")
        assert "webdriver" in content

    def test_chrome_runtime_patches(self):
        content = _read_stealth("chrome_runtime.js")
        assert "chrome.runtime" in content or "chrome.csi" in content

    def test_canvas_uses_seeded_prng(self):
        content = _read_stealth("canvas_fingerprint.js")
        assert "__stealth_seed" in content

    def test_webgl_overrides_renderer(self):
        content = _read_stealth("webgl_override.js")
        assert "UNMASKED_RENDERER_WEBGL" in content or "UNMASKED_VENDOR_WEBGL" in content

    def test_timezone_overrides_intl(self):
        content = _read_stealth("timezone.js")
        assert "__stealth_timezone" in content or "DateTimeFormat" in content

    def test_mouse_exposes_generate_path(self):
        content = _read_stealth("mouse_movement.js")
        assert "generateMousePath" in content

    def test_keyboard_exposes_generate_delays(self):
        content = _read_stealth("keyboard_timing.js")
        assert "generateKeyDelays" in content

    def test_scripts_are_nonempty(self):
        for filename in EXPECTED_FILES:
            content = _read_stealth(filename)
            assert len(content.strip()) > 20, f"{filename} appears empty or too short"
