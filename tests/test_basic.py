from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import configreader as configreader_pkg
from configreader.configreader import ConfigReader
from configreader.configreader import ConfigSource


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
    monkeypatch.setenv("AIMSIM_314_HOST", "env-host")
    reader = ConfigReader(
        dictionary={"DEFAULT": {"host": "dict-host"}},
        env_default_section="aimsim_314",
        providers=["env", "dict"],
    )
    assert reader.get("host") == "env-host"


def test_env_section_naming(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AIMSIM_314_TIMEOUT", "45")
    reader = ConfigReader(use_env=True, env_default_section="aimsim_314", providers=["env"])
    assert reader.getint("timeout") == 45


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


def test_sections_merges_ini_dict_and_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    ini_path = tmp_path / "settings.ini"
    ini_path.write_text("[app]\nworkers=4\n", encoding="utf-8")
    monkeypatch.setenv("AIMSIM_314_TIMEOUT", "30")

    reader = ConfigReader(
        file=ini_path,
        dictionary={"custom": {"flag": "yes"}},
        env_default_section="aimsim_314",
        providers=["ini", "dict", "env"],
    )

    sections = reader.sections()
    assert "APP" in sections
    assert "CUSTOM" in sections
    assert "AIMSIM_314" in sections


def test_variables_merges_ini_dict_and_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    ini_path = tmp_path / "settings.ini"
    ini_path.write_text("[aimsim_314]\nworkers=4\n", encoding="utf-8")
    monkeypatch.setenv("AIMSIM_314_TIMEOUT", "45")

    reader = ConfigReader(
        file=ini_path,
        dictionary={"aimsim_314": {"mode": "prod"}},
        env_default_section="aimsim_314",
        providers=["dict", "ini", "env"],
    )

    names = reader.variables("aimsim_314")
    assert "WORKERS" in names
    assert "MODE" in names
    assert "TIMEOUT" in names


def test_cached_dictionary_snapshot_and_refresh():
    source = {"DEFAULT": {"host": "one"}}
    reader = ConfigReader(dictionary=source, providers=["dict"], cached=True) # pyright: ignore[reportArgumentType]

    source["DEFAULT"]["host"] = "two"
    assert reader.get("host") == "one"

    reader.refresh()
    assert reader.get("host") == "two"


def test_non_cached_dictionary_reads_live_value():
    source = {"DEFAULT": {"host": "one"}}
    reader = ConfigReader(dictionary=source, providers=["dict"], cached=False) # pyright: ignore[reportArgumentType]

    source["DEFAULT"]["host"] = "two"
    assert reader.get("host") == "two"


def test_cache_method_creates_cache_when_missing_with_warning():
    source = {"DEFAULT": {"host": "one"}}
    reader = ConfigReader(dictionary=source, providers=["dict"], cached=False) # pyright: ignore[reportArgumentType]

    with pytest.warns(RuntimeWarning, match="Cache does not exist"):
        reader.cache()

    source["DEFAULT"]["host"] = "two"
    assert reader.get("host") == "one"


def test_refresh_raises_when_cache_missing_and_raise_mode():
    source = {"DEFAULT": {"host": "one"}}
    reader = ConfigReader(dictionary=source, providers=["dict"], cached=False) # pyright: ignore[reportArgumentType]

    with pytest.raises(RuntimeError, match="Cache does not exist"):
        reader.refresh(on_cache_exists="raise")


def test_copy_cache_true_copies_source_cache_snapshot():
    source = {"DEFAULT": {"host": "one"}}
    reader = ConfigReader(dictionary=source, providers=["dict"], cached=True) # pyright: ignore[reportArgumentType]

    source["DEFAULT"]["host"] = "two"
    clone = reader.copy(copy_cache=True)

    assert clone.get("host") == "one"



def test_package_exposes_version():
    assert hasattr(configreader_pkg, "__version__")
    assert isinstance(configreader_pkg.__version__, str)
    assert configreader_pkg.__version__
