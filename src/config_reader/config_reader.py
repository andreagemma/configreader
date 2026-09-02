from __future__ import annotations

import os
import ast
import configparser
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
        dictionary: dict[str, dict[str, str]] | None = None,
        db_url: str | None = None,
        db_query: str | None = None,
        use_env: bool = True,
        providers: list[ConfigSource | str] | None = None,
    ):
        """Initialize the reader with one or more configuration providers.

        Args:
            file: Optional path to an INI file.
            dictionary: Optional nested dictionary grouped by section and key.
            db_url: Optional SQLAlchemy database URL.
            db_query: Optional SQL query with :section and :name bind parameters.
            use_env: Enable or disable environment variable lookup.
            providers: Provider priority order. Accepts ConfigSource values or strings.

        Raises:
            FileNotFoundError: If file is provided and does not exist.
            ImportError: If DB provider is enabled and SQLAlchemy is unavailable.
        """
        self.config = configparser.ConfigParser()

        # File .ini
        self.use_ini = file is not None

        if self.use_ini:
            file_name: str = str(file)
            if os.path.exists(file_name):
                self.config.read(file_name)
            else:
                raise FileNotFoundError(f"INI file '{file_name}' does not exist")

        self.use_db = db_url is not None
        self.db_url = db_url
        self.db_query = db_query or "SELECT value FROM settings WHERE section = :section AND name = :name"
        self.db_session = None

        self.use_env = use_env

        self.use_dict = dictionary is not None
        self.dictionary = dictionary

        if self.use_db and self.db_url:
            self._init_db()

        # Keep provider ordering explicit and stable while avoiding mutable defaults.
        if providers is None:
            providers = [ConfigSource.INI, ConfigSource.DB, ConfigSource.ENV, ConfigSource.DICT]
        self.order = [p if isinstance(p, ConfigSource) else ConfigSource.parse(p) for p in providers]

    def items(self):
        """Iterate over all entries loaded from the INI provider.

        Yields:
            Tuples in the form (section, name, value).

        Raises:
            None.
        """
        for sec in self.config.sections():
            for name, value in self.config.items(sec):
                yield sec, name, value

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
            - DEFAULT section: NAME
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
        # DEFAULT uses NAME; custom sections use SECTION_NAME.
        if section.upper() == "DEFAULT":
            return os.getenv(name.upper())
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
