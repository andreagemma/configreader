# API Reference

## ConfigSource Enum

Available values:
- ConfigSource.INI ("ini")
- ConfigSource.DB ("db")
- ConfigSource.ENV ("env")
- ConfigSource.DICT ("dict")

Methods:
- ConfigSource.parse(value: str) -> ConfigSource | None

## ConfigReader Class

### Constructor

```python
ConfigReader(
    file: str | Path | None = None,
    dictionary: dict[str, dict[str, str]] | None = None,
    db_url: str | None = None,
    db_query: str | None = None,
    use_env: bool = True,
    env_default_section: str = "DEFAULT",
    providers: list[ConfigSource | str] | None = None,
    cached: bool = True,
)
```

Parameters:
- file: path to an INI file.
- dictionary: in-memory source grouped by section and key.
- db_url: SQLAlchemy database URL.
- db_query: SQL query using :section and :name parameters.
- use_env: enable or disable environment variable lookup.
- env_default_section: prefix used when reading fallback environment variables for the default section. Defaults to "DEFAULT".
- providers: provider precedence order.
- cached: when True, builds startup cache and reads `get/items/sections/variables` from cache.

### Main Methods

- get(name, default=None, section="DEFAULT") -> str | None
: reads the raw value as string.

- getint(name, default=None, section="DEFAULT") -> int | None
: converts using int(...).

- getboolean(name, default=None, section="DEFAULT") -> bool | None
: returns True when lowercased value is in ("true", "1", "yes"), else False.

- getfloat(name, default=None, section="DEFAULT") -> float | None
: converts using float(...).

- getlist(name, default=None, section="DEFAULT") -> list[Any] | None
: parses with ast.literal_eval(...).

- getset(name, default=None, section="DEFAULT") -> set[Any] | None
: parses with set(ast.literal_eval(...)).

- gettuple(name, section="DEFAULT", default=None) -> tuple[Any, ...] | None
: parses with tuple(ast.literal_eval(...)).

- getdict(name, section="DEFAULT", default=None) -> dict[Any, Any] | None
: parses with dict(ast.literal_eval(...)).

- items()
: iterator of (section, name, value) from loaded INI sections.

- sections() -> list[str]
: returns merged, unique section names (uppercase) across enabled providers.

- variables(section: str) -> list[str]
: returns merged, unique option names (uppercase) for a section across enabled providers.

- refresh(on_cache_exists: str = "warining") -> None
: reloads providers and rebuilds cache.

- cache(on_cache_exists: str = "warining") -> None
: creates cache dictionaries on demand.

- copy(copy_cache: bool = False, on_cache_exists: str = "warining") -> ConfigReader
: clones the reader; cache copy is optional and on demand.

### DB Utility Static Methods

- ConfigReader.check_db_connection(db_url: str) -> bool
- ConfigReader.check_db_exists(db_url: str, table_name: str = "settings") -> bool

## Important Behavior

- If no provider returns a value, default is returned.
- With `cached=True`, values are read from startup cache until `refresh()` or `cache()` is called.
- Typed conversions may raise parsing/conversion exceptions.
- Without SQLAlchemy, DB methods are unavailable.
- `on_cache_exists` supports `"ignore"`, `"raise"`, `"warning"`. The default literal is `"warining"`, normalized to `"warning"`.