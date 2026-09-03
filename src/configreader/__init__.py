"""configreader package
Simple library functions for the project.
"""

from ._version import __version__
from .configreader import ConfigReader, ConfigSource

__all__ = ["__version__", "ConfigReader", "ConfigSource"]
