from __future__ import annotations

import re

import configreader
from configreader._version import __version__


def test_public_version_uses_code_source() -> None:
    assert configreader.__version__ == __version__
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[a-zA-Z0-9.+-]*)?", __version__)
