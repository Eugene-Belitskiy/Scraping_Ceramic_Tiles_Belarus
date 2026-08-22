import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "Altagamma"))

import Altagamma


def test_make_options_headless_in_ci(monkeypatch):
    monkeypatch.setenv("CI", "true")
    options = Altagamma.make_options()
    assert "--headless=new" in options.arguments


def test_make_options_not_headless_locally(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    options = Altagamma.make_options()
    assert "--headless=new" not in options.arguments
