from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import config_reader as config_reader_pkg
from config_reader.config_reader import ConfigReader
from config_reader.config_reader import ConfigSource


def test_get_from_dict_and_typed_accessors():
    reader = ConfigReader(
        dictionary={
            "DEFAULT": {
                "host": "localhost",
                "port": "5432",
                "enabled": "yes",
                "ratio": "0.25",
                "items": "[1, 2, 3]",
                "labels": "{'a', 'b'}",
                "coords": "(10, 20)",
                "mapping": "{'k': 'v'}",
            }
        },
        providers=[ConfigSource.DICT],
    )

    assert reader.get("host") == "localhost"
    assert reader.getint("port") == 5432
    assert reader.getboolean("enabled") is True
    assert reader.getfloat("ratio") == 0.25
    assert reader.getlist("items") == [1, 2, 3]
    assert reader.getset("labels") == {"a", "b"}
    assert reader.gettuple("coords") == (10, 20)
    assert reader.getdict("mapping") == {"k": "v"}


def test_provider_priority_env_over_dict(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOST", "env-host")
    reader = ConfigReader(
        dictionary={"DEFAULT": {"host": "dict-host"}},
        providers=["env", "dict"],
    )
    assert reader.get("host") == "env-host"


def test_env_section_naming(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_TIMEOUT", "45")
    reader = ConfigReader(use_env=True, providers=["env"])
    assert reader.getint("timeout", section="app") == 45


def test_default_returned_when_missing():
    reader = ConfigReader(use_env=False, providers=["env", "dict"])
    assert reader.get("missing", default="fallback") == "fallback"
    assert reader.getint("missing_int", default=7) == 7


def test_missing_ini_file_raises():
    with pytest.raises(FileNotFoundError):
        ConfigReader(file="this_file_should_not_exist.ini")


def test_items_iterates_ini_sections(tmp_path: Path):
    ini_path = tmp_path / "settings.ini"
    ini_path.write_text("[app]\nworkers=4\nmode=prod\n", encoding="utf-8")

    reader = ConfigReader(file=ini_path, providers=["ini"])
    items = set(reader.items())

    assert ("app", "workers", "4") in items
    assert ("app", "mode", "prod") in items


def test_package_exposes_version():
    assert hasattr(config_reader_pkg, "__version__")
    assert isinstance(config_reader_pkg.__version__, str)
    assert config_reader_pkg.__version__
