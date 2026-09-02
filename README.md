# config_reader

Python library to read configuration values from multiple sources with configurable precedence.

Supported sources:
- INI file
- SQL database through SQLAlchemy (optional)
- environment variables
- in-memory Python dictionary

Values are resolved in order, and the first non-empty match is returned.

## Installation

### From PyPI

```bash
pip install config_reader
```

### From source

```bash
git clone https://github.com/andreagemma/config_reader.git
cd config_reader
pip install -e .
```

### Database support (optional)

Install SQLAlchemy if you want to use the DB provider:

```bash
pip install sqlalchemy
```

Or install the project with DB extras:

```bash
pip install "config_reader[db]"
```

## Quickstart

```python
from config_reader import ConfigReader

reader = ConfigReader(
    file="config.ini",
    use_env=True,
    dictionary={"DEFAULT": {"timeout": "30"}},
    providers=["env", "ini", "dict"],
)

host = reader.get("host", default="127.0.0.1")
port = reader.getint("port", default=8080)
debug = reader.getboolean("debug", default=False)
```

## Provider Precedence

The providers list defines lookup order.

Example:

```python
providers = ["env", "db", "ini", "dict"]
```

Meaning:
1. check environment first
2. then check database
3. then check INI file
4. then check dictionary

## Environment Variables

Naming rules:
- if section="DEFAULT", variable name is NAME
- for custom sections, variable name is SECTION_NAME

Examples:
- reader.get("host", section="DEFAULT") reads HOST
- reader.get("host", section="app") reads APP_HOST

## Using INI Files

Example config.ini:

```ini
[DEFAULT]
host = localhost
port = 5432
debug = true
items = [1, 2, 3]

[app]
workers = 4
```

Code:

```python
reader = ConfigReader(file="config.ini")

host = reader.get("host")
port = reader.getint("port")
debug = reader.getboolean("debug")
items = reader.getlist("items")
workers = reader.getint("workers", section="app")
```

## Using a Dictionary

```python
reader = ConfigReader(
    dictionary={
        "DEFAULT": {
            "host": "localhost",
            "allowed": "['admin', 'user']",
        },
        "service": {
            "retries": "3",
        },
    },
    providers=["dict"],
)

allowed = reader.getlist("allowed")
retries = reader.getint("retries", section="service")
```

## Using a Database

Constructor:

```python
reader = ConfigReader(
    db_url="sqlite:///settings.db",
    db_query="SELECT value FROM settings WHERE section = :section AND name = :name",
    providers=["db", "env"],
)
```

Default query shape:

```sql
SELECT value FROM settings WHERE section = :section AND name = :name
```

DB utility methods:

```python
ok = ConfigReader.check_db_connection("sqlite:///settings.db")
exists = ConfigReader.check_db_exists("sqlite:///settings.db", table_name="settings")
```

## Main API

- `get(name, default=None, section="DEFAULT") -> str | None`
- `getint(name, default=None, section="DEFAULT") -> int | None`
- `getboolean(name, default=None, section="DEFAULT") -> bool | None`
- `getfloat(name, default=None, section="DEFAULT") -> float | None`
- `getlist(name, default=None, section="DEFAULT") -> list[Any] | None`
- `getset(name, default=None, section="DEFAULT") -> set[Any] | None`
- `gettuple(name, default=None, section="DEFAULT") -> tuple[Any, ...] | None`
- `getdict(name, default=None, section="DEFAULT") -> dict[Any, Any] | None`
- `items()` iterator over loaded INI entries

Full details in [docs/api.md](docs/api.md).

## Errors And Type Conversion

- `FileNotFoundError` is raised if the provided INI file does not exist.
- Typed getters (`getint`, `getfloat`, `getlist`, etc.) propagate parsing/conversion errors.
- If SQLAlchemy is not installed, DB features are unavailable.

## Development

Install development dependencies:

```bash
pip install -e .[dev]
```

Run tests:

```bash
pytest
```

## More Documentation

- [docs/overview.md](docs/overview.md)
- [docs/providers.md](docs/providers.md)
- [docs/api.md](docs/api.md)
- [docs/examples.md](docs/examples.md)

## License

Distributed under the MIT License. See [LICENSE](LICENSE).
