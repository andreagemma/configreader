from __future__ import annotations

import os
import ast
import configparser
import warnings
from enum import Enum
from pathlib import Path
from typing import Any

try:
    from sqlalchemy import create_engine
    from sqlalchemy import inspect
    from sqlalchemy import text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.exc import SQLAlchemyError
except Exception:
    create_engine = None
    inspect = None
    text = None
    sessionmaker = None
    SQLAlchemyError = Exception


class ConfigSource(Enum):
    """Supported configuration providers.

    Attributes:
        INI: Read values from an INI file.
        DB: Read values from a database using SQLAlchemy.
        ENV: Read values from environment variables.
        DICT: Read values from an in-memory dictionary.
    """

    INI = "ini"
    DB = "db"
    ENV = "env"
    DICT = "dict"

    @classmethod
    def parse(cls, value: str) -> ConfigSource | None:
        """Parse a provider string into a ConfigSource enum value.

        Args:
            value: Provider name (e.g. "ini", "db", "env", "dict").

        Returns:
            The matching ConfigSource member, or None if unsupported.

        Raises:
            None.
        """
        for item in cls:
            if item.value == value:
                return item
        return None

    def __str__(self) -> str:
        """Return the provider name as a string.

        Returns:
            The provider value (e.g. "ini", "db", "env", "dict").

        Raises:
            None.
        """
        return self.value


class ConfigReader:
    """Read configuration values from multiple providers with fallback order.

    The reader checks providers in order and returns the first non-None value.
    """

    def __init__(
        self,
        file: str | Path | None = None,
        dictionary: dict[str, dict[str, str | int | float | bool | None]] | None = None,
        db_url: str | None = None,
        db_query: str | None = None,
        use_env: bool = True,
        env_default_section: str = "DEFAULT",
        providers: list[ConfigSource | str] | None = None,
        cached: bool = True,
    ):
        """Initialize the reader with one or more configuration providers.

        Args:
            file: Optional path to an INI file.
            dictionary: Optional nested dictionary grouped by section and key.
            db_url: Optional SQLAlchemy database URL.
            db_query: Optional SQL query with :section and :name bind parameters.
            use_env: Enable or disable environment variable lookup.
            env_default_section: Section name used for environment variable prefixing (e.g. "APP" for variable names like APP_FOO).
                Will be used as the default section when reading environment variables.
            providers: Provider priority order. Accepts ConfigSource values or strings.
            cached: Build an in-memory cache at initialization and read values from cache.

        Raises:
            FileNotFoundError: If file is provided and does not exist.
            ImportError: If DB provider is enabled and SQLAlchemy is unavailable.
        """
        self.file = Path(file) if file is not None else None
        self.config = configparser.ConfigParser()
        providers = providers or [ConfigSource.DICT, ConfigSource.ENV, ConfigSource.DB, ConfigSource.INI]
        tmp_order = [p if isinstance(p, ConfigSource) else ConfigSource.parse(p) for p in providers]
        self.order: list[ConfigSource | str] = [x for x in tmp_order if x is not None]
        self.use_db = db_url is not None and ConfigSource.DB in self.order
        self.use_ini = file is not None and ConfigSource.INI in self.order
        self.use_env = use_env and ConfigSource.ENV in self.order

        # File .ini

        if self.use_ini:
            file_name: str = str(file)
            if os.path.exists(file_name):
                self.config.read(file_name)
            else:
                raise FileNotFoundError(f"INI file '{file_name}' does not exist")

        self.db_url = db_url
        self.db_query = db_query or "SELECT value FROM settings WHERE section = :section AND name = :name"
        self.db_session = None

        self.use_dict = dictionary is not None
        self.dictionary = dictionary

        if self.use_db and self.db_url:
            self._init_db()
        self.env_default_section = env_default_section
        self.cached = cached
        self._cache_ready = False
        self._cache_values: dict[ConfigSource, dict[str, dict[str, str]]] = {}
        self._cache_env_values: dict[str, str] = {}
        self._cache_ini_items: list[tuple[str, str, str]] = []

        if self.cached:
            self._build_cache()

    @staticmethod
    def _normalize_cache_mode(on_cache_exists: str) -> str:
        value = on_cache_exists.strip().lower()
        if value == "warining":
            return "warning"
        if value not in {"ignore", "raise", "warning"}:
            raise ValueError("on_cache_exists must be one of: 'ignore', 'raise', 'warning'")
        return value

    def _handle_missing_cache(self, action: str, on_cache_exists: str) -> None:
        mode = self._normalize_cache_mode(on_cache_exists)
        if mode == "ignore":
            return
        message = f"Cache does not exist; '{action}' will create or skip cache data."
        if mode == "raise":
            raise RuntimeError(message)
        warnings.warn(message, RuntimeWarning, stacklevel=2)

    @staticmethod
    def _norm_key(value: str) -> str:
        return str(value).upper()

    def _build_cache(self) -> None:
        provider_cache: dict[ConfigSource, dict[str, dict[str, str]]] = {
            ConfigSource.INI: {},
            ConfigSource.DB: {},
            ConfigSource.DICT: {},
        }
        env_cache: dict[str, str] = {}
        ini_items: list[tuple[str, str, str]] = []

        if self.use_dict and self.dictionary:
            for section, values in self.dictionary.items():
                sec_key = self._norm_key(str(section))
                section_cache = provider_cache[ConfigSource.DICT].setdefault(sec_key, {})
                for name, value in values.items():
                    section_cache[self._norm_key(str(name))] = str(value)

        if self.use_ini:
            defaults = self.config.defaults()
            if defaults:
                default_cache = provider_cache[ConfigSource.INI].setdefault("DEFAULT", {})
                for name, value in defaults.items():
                    default_cache[self._norm_key(name)] = str(value)

            for section in self.config.sections():
                sec_key = self._norm_key(section)
                section_cache = provider_cache[ConfigSource.INI].setdefault(sec_key, {})
                for name, value in self.config.items(section):
                    name_key = self._norm_key(name)
                    text_value = str(value)
                    section_cache[name_key] = text_value
                    ini_items.append((section, name, text_value))

        if self.use_db and self.db_session and text is not None:
            for section in self._sections_from_db():
                section_cache = provider_cache[ConfigSource.DB].setdefault(section, {})
                for name in self._names_from_db(section):
                    value = self._get_from_db(section, name)
                    if value is not None:
                        section_cache[self._norm_key(name)] = str(value)

        if self.use_env:
            env_cache = {self._norm_key(key): str(value) for key, value in os.environ.items()}

        self._cache_values = provider_cache
        self._cache_env_values = env_cache
        self._cache_ini_items = ini_items
        self._cache_ready = True

    def _get_from_cache(self, section: str, name: str) -> str | None:
        section_key = self._norm_key(section)
        name_key = self._norm_key(name)
        for provider in self.order:
            if provider == ConfigSource.ENV:
                if not self.use_env:
                    continue
                section_name = section.strip()
                default_key = f"{self.env_default_section}_{name}".upper()
                if section_name == "":
                    value = self._cache_env_values.get(name_key, self._cache_env_values.get(default_key))
                elif section_name.upper() == "DEFAULT":
                    value = self._cache_env_values.get(default_key)
                else:
                    value = self._cache_env_values.get(f"{section}_{name}".upper())
                if value is not None:
                    return value
                continue

            if provider in {ConfigSource.INI, ConfigSource.DB, ConfigSource.DICT}:
                provider_cache = self._cache_values.get(provider, {})
                value = provider_cache.get(section_key, {}).get(name_key)
                if value is not None:
                    return value

        return None

    def cache(self, on_cache_exists: str = "warining") -> None:
        """Create cache dictionaries for all enabled providers.

        Args:
            on_cache_exists: Policy used when cache is not yet available. One of
                "ignore", "raise", "warning" (also accepts legacy typo "warining").

        Raises:
            RuntimeError: If on_cache_exists="raise" and cache does not exist.
            ValueError: If on_cache_exists has an invalid value.
        """
        if not self._cache_ready:
            self._handle_missing_cache(action="cache", on_cache_exists=on_cache_exists)
        self.cached = True
        self._build_cache()

    def refresh(self, on_cache_exists: str = "warining") -> None:
        """Reload provider data and rebuild cache.

        Args:
            on_cache_exists: Policy used when cache is not yet available. One of
                "ignore", "raise", "warning" (also accepts legacy typo "warining").

        Raises:
            FileNotFoundError: If the configured INI file no longer exists.
            RuntimeError: If on_cache_exists="raise" and cache does not exist.
            ValueError: If on_cache_exists has an invalid value.
        """
        if self.use_ini:
            if self.file is None:
                raise FileNotFoundError("INI file path is not configured")
            if not self.file.exists():
                raise FileNotFoundError(f"INI file '{self.file}' does not exist")
            self.config = configparser.ConfigParser()
            self.config.read(str(self.file))

        if self.use_db and self.db_session is None and self.db_url:
            self._init_db()

        if not self._cache_ready:
            self._handle_missing_cache(action="refresh", on_cache_exists=on_cache_exists)
        self.cached = True
        self._build_cache()

    def items(self):
        """Iterate over all entries loaded from the INI provider.

        Yields:
            Tuples in the form (section, name, value).

        Raises:
            None.
        """
        if self.cached:
            for sec, name, value in self._cache_ini_items:
                yield sec, name, value
            return

        for sec in self.config.sections():
            for name, value in self.config.items(sec):
                yield sec, name, value

    def _sections_from_ini(self) -> list[str]:
        if not self.use_ini:
            return []
        return [sec.upper() for sec in self.config.sections()]

    def _sections_from_dict(self) -> list[str]:
        if not self.use_dict or not self.dictionary:
            return []
        return [str(sec).upper() for sec in self.dictionary.keys()]

    def _sections_from_db(self) -> list[str]:
        if not self.use_db or not self.db_session or text is None:
            return []
        try:
            rows = self.db_session.execute(text("SELECT DISTINCT section FROM settings")).all()
            return [str(row[0]).upper() for row in rows if row and row[0] is not None]
        except SQLAlchemyError:
            return []

    def _sections_from_env(self) -> list[str]:
        if not self.use_env:
            return []
        return (
            [self.env_default_section.upper()]
            if any(key.upper().startswith(f"{self.env_default_section.upper()}_") for key in os.environ.keys())
            else []
        )

    def sections(self) -> list[str]:
        """Return merged section names across enabled providers.

        Returns:
            Sorted list of unique section names (uppercase).
        """
        merged: set[str] = set()
        if self.cached:            
            for provider in self.order:
                if provider in {ConfigSource.INI, ConfigSource.DB, ConfigSource.DICT}:
                    merged.update(self._cache_values.get(provider, {}).keys())
                elif provider == ConfigSource.ENV and self.use_env:
                    prefix = f"{self.env_default_section.upper()}_"
                    if any(key.startswith(prefix) for key in self._cache_env_values.keys()):
                        merged.add(self.env_default_section.upper())
            return sorted(merged)

        for provider in self.order:
            if provider == ConfigSource.INI:
                merged.update(self._sections_from_ini())
            elif provider == ConfigSource.DB:
                merged.update(self._sections_from_db())
            elif provider == ConfigSource.ENV:
                merged.update(self._sections_from_env())
            elif provider == ConfigSource.DICT:
                merged.update(self._sections_from_dict())
        return sorted(merged)

    def _names_from_ini(self, section: str) -> list[str]:
        if not self.use_ini:
            return []
        sec = section.upper()
        if sec == "DEFAULT":
            return [name.upper() for name in self.config.defaults().keys()]
        if not self.config.has_section(section) and not self.config.has_section(sec):
            return []
        target = section if self.config.has_section(section) else sec
        return [name.upper() for name in self.config.options(target)]

    def _names_from_dict(self, section: str) -> list[str]:
        if not self.use_dict or not self.dictionary:
            return []
        sec = section.upper()
        for key, values in self.dictionary.items():
            if str(key).upper() == sec:
                return [str(name).upper() for name in values.keys()]
        return []

    def _names_from_db(self, section: str) -> list[str]:
        if not self.use_db or not self.db_session or text is None:
            return []
        try:
            rows = self.db_session.execute(
                text("SELECT DISTINCT name FROM settings WHERE section = :section"),
                {"section": section},
            ).all()
            if not rows and section != section.upper():
                rows = self.db_session.execute(
                    text("SELECT DISTINCT name FROM settings WHERE section = :section"),
                    {"section": section.upper()},
                ).all()
            return [str(row[0]).upper() for row in rows if row and row[0] is not None]
        except SQLAlchemyError:
            return []

    def _names_from_env(self, section: str) -> list[str]:
        if not self.use_env:
            return []
        sec = section.upper()
        names: set[str] = set()
        prefix = f"{sec}_"
        for key in os.environ.keys():
            up = key.upper()
            if up.startswith(prefix):
                names.add(up[len(prefix) :])
        return sorted(names)

    def variables(self, section: str) -> list[str]:
        """Return merged option names for one section across providers.

        Args:
            section: Section name.

        Returns:
            Sorted list of unique variable names (uppercase).
        """
        merged: set[str] = set()
        if self.cached:
            sec_key = section.upper()
            for provider in self.order:
                if provider in {ConfigSource.INI, ConfigSource.DB, ConfigSource.DICT}:
                    merged.update(self._cache_values.get(provider, {}).get(sec_key, {}).keys())
                elif provider == ConfigSource.ENV and self.use_env:
                    prefix = f"{sec_key}_"
                    for key in self._cache_env_values.keys():
                        if key.startswith(prefix):
                            merged.add(key[len(prefix) :])
            return sorted(merged)

        for provider in self.order:
            if provider == ConfigSource.INI:
                merged.update(self._names_from_ini(section))
            elif provider == ConfigSource.DB:
                merged.update(self._names_from_db(section))
            elif provider == ConfigSource.ENV:
                merged.update(self._names_from_env(section))
            elif provider == ConfigSource.DICT:
                merged.update(self._names_from_dict(section))
        return sorted(merged)

    def _init_db(self):
        """Create and store a SQLAlchemy session for DB lookups.

        Raises:
            ImportError: If SQLAlchemy is not installed.
            ValueError: If db_url is missing.

        Notes:
            SQLAlchemy runtime connection errors are caught and logged, and do not
            raise further exceptions from this method.
        """
        if create_engine is None or sessionmaker is None:
            raise ImportError("SQLAlchemy is not available")
        if not self.db_url:
            raise ValueError("Database URL is not provided")
        try:
            engine = create_engine(self.db_url)
            Session = sessionmaker(bind=engine)
            self.db_session = Session()
        except SQLAlchemyError as ex:
            print(f"Error initializing database connection: {ex}")

    @staticmethod
    def check_db_connection(db_url: str) -> bool:
        """Check whether a DB connection can be established for a URL.

        Args:
            db_url: SQLAlchemy connection URL.

        Returns:
            True if a connection can be opened, False otherwise.

        Raises:
            None.
        """
        if create_engine is None:
            return False
        try:
            engine = create_engine(db_url)
            with engine.connect() as connection:
                connection.close()
            return True
        except SQLAlchemyError:
            return False

    @staticmethod
    def check_db_exists(db_url: str, table_name: str = "settings") -> bool:
        """Check whether a table exists in the target database.

        Args:
            db_url: SQLAlchemy connection URL.
            table_name: Table to check for existence.

        Returns:
            True if the table exists, False otherwise.

        Raises:
            None.
        """
        if create_engine is None or inspect is None:
            return False
        try:
            engine = create_engine(db_url)
            inspector = inspect(engine)
            return inspector.has_table(table_name)
        except SQLAlchemyError:
            return False

    def _get_from_dict(self, section: str, name: str) -> str | None:
        """Read a value from the dictionary provider.

        Args:
            section: Configuration section.
            name: Configuration key.

        Returns:
            Value converted to string if found, otherwise None.

        Raises:
            None.
        """
        if not self.use_dict:
            return None
        if not self.dictionary:
            return None
        value = self.dictionary.get(section, {}).get(name)
        return str(value) if value is not None else None

    def _get_from_db(self, section: str, name: str) -> str | None:
        """Read a value from the database provider.

        Args:
            section: Configuration section.
            name: Configuration key.

        Returns:
            Database value as string if found, otherwise None.

        Raises:
            None.

        Notes:
            SQLAlchemy runtime errors are caught and logged.
        """
        if not self.use_db:
            return None
        if not self.db_session:
            return None
        if text is None:
            return None
        try:
            statement = text(self.db_query)
            result = self.db_session.execute(statement, {"name": name, "section": section}).scalar_one_or_none()
            return result if isinstance(result, str) else (str(result) if result is not None else None)
        except SQLAlchemyError as ex:
            print(f"Error fetching {name} from database: {ex}")
            return None

    def _get_from_ini(self, section: str, name: str) -> str | None:
        """Read a value from the INI provider using ConfigParser fallback.

        Args:
            section: Configuration section.
            name: Configuration key.

        Returns:
            INI value if found, otherwise None.

        Raises:
            None.
        """
        if not self.use_ini:
            return None
        return self.config.get(section, name, fallback=None)

    def _get_from_env(self, section: str, name: str) -> str | None:
        """Read a value from environment variables.

        Naming convention:
            - DEFAULT section: ENV_DEFAULT_SECTION_NAME
            - Empty section: NAME, then ENV_DEFAULT_SECTION_NAME
            - Custom section: SECTION_NAME

        Args:
            section: Configuration section.
            name: Configuration key.

        Returns:
            Environment variable value if found, otherwise None.

        Raises:
            None.
        """
        if not self.use_env:
            return None
        section_name = section.strip()
        default_key = f"{self.env_default_section}_{name}".upper()
        if section_name == "":
            return os.getenv(name.upper(), os.getenv(default_key))
        if section_name.upper() == "DEFAULT":
            return os.getenv(default_key)
        return os.getenv(f"{section}_{name}".upper())

    def get(self, name: str, default: str | None = None, section: str = "DEFAULT") -> str | None:
        """Resolve a configuration value using provider priority order.

        Args:
            name: Key name inside the section.
            default: Value returned when no provider has a value.
            section: Configuration section.

        Returns:
            The first resolved value as a string, otherwise default.

        Raises:
            None.
        """
        if self.cached:
            value = self._get_from_cache(section=section, name=name)
            return value if value is not None else default

        value = None
        # Providers are queried in order; first non-None wins.
        for provider in self.order:
            if provider == ConfigSource.INI:
                value = self._get_from_ini(section, name)
            elif provider == ConfigSource.DB:
                value = self._get_from_db(section, name)
            elif provider == ConfigSource.ENV:
                value = self._get_from_env(section, name)
            elif provider == ConfigSource.DICT:
                value = self._get_from_dict(section, name)

            if value is not None:
                break

        return value if value is not None else default

    def getint(self, name: str, default: int | None = None, section: str = "DEFAULT") -> int | None:
        """Get a value and convert it to int.

        Args:
            name: Configuration key.
            default: Returned when no value is found.
            section: Configuration section.

        Returns:
            Parsed integer value, or default if unresolved.

        Raises:
            ValueError: If the resolved value cannot be converted to int.
            TypeError: If the resolved value type is not compatible with int().
        """
        value = self.get(name, section=section, default=None)
        return int(value) if value is not None else default

    def getboolean(self, name: str, default: bool | None = None, section: str = "DEFAULT") -> bool | None:
        """Get a value and convert it to bool.

        Truthy values are: "true", "1", "yes" (case-insensitive).

        Args:
            name: Configuration key.
            default: Returned when no value is found.
            section: Configuration section.

        Returns:
            True for truthy strings, False for other resolved strings,
            or default if unresolved.

        Raises:
            None.
        """
        value = self.get(name, section=section, default=None)
        return value.lower() in ("true", "1", "yes") if value is not None else default

    def getfloat(self, name: str, default: float | None = None, section: str = "DEFAULT") -> float | None:
        """Get a value and convert it to float.

        Args:
            name: Configuration key.
            default: Returned when no value is found.
            section: Configuration section.

        Returns:
            Parsed float value, or default if unresolved.

        Raises:
            ValueError: If the resolved value cannot be converted to float.
            TypeError: If the resolved value type is not compatible with float().
        """
        value = self.get(name, section=section, default=None)
        return float(value) if value is not None else default

    def getlist(self, name: str, default: list[Any] | None = None, section: str = "DEFAULT") -> list[Any] | None:
        """Get a value and parse it as a Python list literal.

        Args:
            name: Configuration key.
            default: Returned when no value is found.
            section: Configuration section.

        Returns:
            Parsed Python object from literal_eval, or default if unresolved.

        Raises:
            ValueError: If the value contains a malformed literal.
            SyntaxError: If the value is not valid Python literal syntax.
            MemoryError: In rare cases for extremely large literals.
        """
        value = self.get(name, section=section, default=None)
        # Complex values are parsed from string literals.
        return ast.literal_eval(value) if value is not None else default

    def getset(self, name: str, default: set[Any] | None = None, section: str = "DEFAULT") -> set[Any] | None:
        """Get a value and parse it as a set.

        If the resolved value is already a set, it is returned as-is.

        Args:
            name: Configuration key.
            default: Returned when no value is found.
            section: Configuration section.

        Returns:
            Parsed set value, or default if unresolved.

        Raises:
            ValueError: If the value contains a malformed literal.
            SyntaxError: If the value is not valid Python literal syntax.
            TypeError: If the parsed value is not iterable for set conversion.
        """
        value = self.get(name, section=section, default=None)
        if isinstance(value, set):
            return value
        return set(ast.literal_eval(value)) if value is not None else default

    def gettuple(
        self, name: str, section: str = "DEFAULT", default: tuple[Any, ...] | None = None
    ) -> tuple[Any, ...] | None:
        """Get a value and parse it as a tuple.

        If the resolved value is already a tuple, it is returned as-is.

        Args:
            name: Configuration key.
            section: Configuration section.
            default: Returned when no value is found.

        Returns:
            Parsed tuple value, or default if unresolved.

        Raises:
            ValueError: If the value contains a malformed literal.
            SyntaxError: If the value is not valid Python literal syntax.
            TypeError: If the parsed value is not iterable for tuple conversion.
        """
        value = self.get(name, section=section, default=None)
        if isinstance(value, tuple):
            return value
        return tuple(ast.literal_eval(value)) if value is not None else default

    def getdict(
        self, name: str, section: str = "DEFAULT", default: dict[Any, Any] | None = None
    ) -> dict[Any, Any] | None:
        """Get a value and parse it as a dictionary.

        If the resolved value is already a dict, it is returned as-is.

        Args:
            name: Configuration key.
            section: Configuration section.
            default: Returned when no value is found.

        Returns:
            Parsed dictionary value, or default if unresolved.

        Raises:
            ValueError: If the value contains a malformed literal.
            SyntaxError: If the value is not valid Python literal syntax.
            TypeError: If the parsed value cannot be converted to dict.
        """
        value = self.get(name, section=section, default=None)
        if isinstance(value, dict):
            return value
        return dict(ast.literal_eval(value)) if value is not None else default

    def copy(self, copy_cache: bool = False, on_cache_exists: str = "warining") -> ConfigReader:
        """Create a new ConfigReader instance with the same settings.

        Args:
            copy_cache: If True, copy the already-built cache to the new instance.
            on_cache_exists: Policy used when source cache does not exist and
                copy_cache=True. One of "ignore", "raise", "warning" (also accepts
                legacy typo "warining").

        Returns:
            A new ConfigReader object with identical configuration sources and order.

        Raises:
            RuntimeError: If on_cache_exists="raise" and cache does not exist.
            ValueError: If on_cache_exists has an invalid value.
        """
        clone = ConfigReader(
            file=self.file,
            dictionary=self.dictionary,
            db_url=self.db_url,
            db_query=self.db_query,
            use_env=self.use_env,
            env_default_section=self.env_default_section,
            providers=self.order,
            cached=self.cached,
        )

        if copy_cache:
            if not self._cache_ready:
                self._handle_missing_cache(action="copy(copy_cache=True)", on_cache_exists=on_cache_exists)
                return clone
            clone._cache_values = {
                provider: {section: values.copy() for section, values in sections.items()}
                for provider, sections in self._cache_values.items()
            }
            clone._cache_env_values = self._cache_env_values.copy()
            clone._cache_ini_items = list(self._cache_ini_items)
            clone._cache_ready = True

        return clone


__all__ = ["ConfigReader", "ConfigSource"]
