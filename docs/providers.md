# Providers

Provider precedence is controlled by the providers argument:

```python
from configreader import ConfigReader

reader = ConfigReader(
    file="config.ini",
    db_url="sqlite:///settings.db",
    use_env=True,
    dictionary={"DEFAULT": {"timeout": "30"}},
    providers=["env", "db", "ini", "dict"],
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
- naming rules:
1. if section="DEFAULT", reads NAME
2. otherwise reads SECTION_NAME

## DICT

- active when dictionary is provided
- expected structure:

```python
{"DEFAULT": {"key": "value"}, "section": {"name": "value"}}
```

Non-string values are internally converted to strings.