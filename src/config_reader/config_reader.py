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
    INI = "ini"
    DB = "db"
    ENV = "env"
    DICT = "dict"

    @classmethod
    def parse(cls, value: str) -> ConfigSource | None:
        for item in cls:
            if item.value == value:
                return item
        return None

    def __str__(self) -> str:
        return self.value

class ConfigReader:
    def __init__(self, 
                 file: str | Path | None = None, 
                 dictionary: dict[str, dict[str, str]] | None = None, 
                 db_url: str | None = None, 
                 db_query: str | None = None, 
                 use_env: bool = True, 
                 providers: list[ConfigSource | str] = [ConfigSource.INI, ConfigSource.DB, ConfigSource.ENV, ConfigSource.DICT]):
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
        self.order = [p if isinstance(p, ConfigSource) else ConfigSource.parse(p) for p in providers]

    def items(self):
        for sec in self.config.sections():
            for name, value in self.config.items(sec):
                yield sec, name, value

    def _init_db(self):
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
        if create_engine is None or inspect is None:
            return False
        try:
            engine = create_engine(db_url)
            inspector = inspect(engine)
            return inspector.has_table(table_name)
        except SQLAlchemyError:
            return False
        
    def _get_from_dict(self, section: str, name: str) -> str | None:
        if not self.use_dict:
            return None
        if not self.dictionary:
            return None
        value = self.dictionary.get(section, {}).get(name)
        return str(value) if value is not None else None

    def _get_from_db(self, section: str, name: str) -> str | None:
        if not self.use_db:
            return None
        if not self.db_session:
            return None
        if text is None:
            return None
        try:
            statement = text(self.db_query)
            result = self.db_session.execute(statement, {'name': name, "section": section}).scalar_one_or_none()
            return result if isinstance(result, str) else (str(result) if result is not None else None)
        except SQLAlchemyError as ex:
            print(f"Error fetching {name} from database: {ex}")
            return None

    def _get_from_ini(self, section: str, name: str) -> str | None:
        if not self.use_ini:
            return None
        return self.config.get(section, name, fallback=None)

    def _get_from_env(self, section:str, name: str) -> str | None:
        if not self.use_env:
            return None
        if section.upper() == "DEFAULT":
            return os.getenv(name.upper())
        return os.getenv(f"{section}_{name}".upper())

    def get(self, name: str, default: str | None = None, section: str = 'DEFAULT') -> str | None:
        value = None
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

    def getint(self, name: str, default: int | None = None, section: str = 'DEFAULT') -> int | None:
        value = self.get(name, section=section, default=None)
        return int(value) if value is not None else default

    def getboolean(self, name: str, default: bool | None = None, section: str = 'DEFAULT') -> bool | None:
        value = self.get(name, section=section, default=None)
        return value.lower() in ('true', '1', 'yes') if value is not None else default

    def getfloat(self, name: str, default: float | None = None, section: str = 'DEFAULT') -> float | None:
        value = self.get(name, section=section, default=None)
        return float(value) if value is not None else default

    def getlist(self, name: str, default: list[Any] | None = None, section: str = 'DEFAULT') -> list[Any] | None:
        value = self.get(name, section=section, default=None)
        return ast.literal_eval(value) if value is not None else default

    def getset(self, name: str, default: set[Any] | None = None, section: str = 'DEFAULT') -> set[Any] | None:
        value = self.get(name, section=section, default=None)
        if isinstance(value, set):
            return value
        return set(ast.literal_eval(value)) if value is not None else default

    def gettuple(self, name: str, section: str = 'DEFAULT', default: tuple[Any, ...] | None = None) -> tuple[Any, ...] | None:
        value = self.get(name, section=section, default=None)
        if isinstance(value, tuple):
            return value
        return tuple(ast.literal_eval(value)) if value is not None else default

    def getdict(self, name: str, section: str = 'DEFAULT', default: dict[Any, Any] | None = None) -> dict[Any, Any] | None:
        value = self.get(name, section=section, default=None)
        if isinstance(value, dict):
            return value
        return dict(ast.literal_eval(value)) if value is not None else default