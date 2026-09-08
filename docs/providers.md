# Providers

Provider precedence is controlled by the providers argument:

```python
from configreader import ConfigReader

reader = ConfigReader(
    file="config.ini",
    db_url="sqlite:///settings.db",
    use_env=True,
    env_default_section="APP",
    dictionary={"DEFAULT": {"timeout": "30"}},
    providers=["env", "db", "ini", "dict"],
    cached=True,
)
```

You can pass either strings ("env") or enum values (ConfigSource.ENV).

## INI

- active when file is provided
- raises FileNotFoundError if the file does not exist
- lookup uses configparser.ConfigParser.get(..., fallback=None)

## DB

- active when db_url is provided
- requires sqlalchemy
- default query:

```sql
SELECT value FROM settings WHERE section = :section AND name = :name
```

- if a SQL error occurs, the provider returns None

## ENV

- active when use_env=True
- names are read as SECTION_NAME
- the default section uses env_default_section as its prefix, which defaults to "DEFAULT"
- pass section="" to read NAME first, with env_default_section_NAME as fallback

## DICT

- active when dictionary is provided
- expected structure:

```python
{"DEFAULT": {"key": "value"}, "section": {"name": "value"}}
```

Non-string values are internally converted to strings.

## Cache

- `cached=True` (default) builds startup cache for enabled providers.
- `get`, `items`, `sections`, and `variables` read from cache when enabled.
- Use `refresh(on_cache_exists="warining")` to reload providers and rebuild cache.
- Use `cache(on_cache_exists="warining")` to build cache on demand when initialized with `cached=False`.