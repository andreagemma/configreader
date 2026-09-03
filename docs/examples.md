# Examples

## 1) Fallback Env -> INI

```python
from configreader import ConfigReader

reader = ConfigReader(
    file="config.ini",
    use_env=True,
    providers=["env", "ini"],
)

api_url = reader.get("api_url", default="http://localhost:8000")
```

With this order, an environment variable overrides the INI value.

## 2) Dictionary Only (useful in tests)

```python
from configreader.configreader import ConfigReader

reader = ConfigReader(
    dictionary={
        "DEFAULT": {
            "retries": "3",
            "enabled": "true",
        },
        "service": {
            "weights": "[0.4, 0.6]",
        },
    },
    providers=["dict"],
)

retries = reader.getint("retries", default=1)
enabled = reader.getboolean("enabled", default=False)
weights = reader.getlist("weights", section="service", default=[1.0])
```

## 3) DB With Custom Query

```python
from configreader.configreader import ConfigReader

reader = ConfigReader(
    db_url="sqlite:///settings.db",
    db_query="""
        SELECT setting_value
        FROM app_settings
        WHERE section = :section AND key_name = :name
    """,
    providers=["db"],
)

timeout = reader.getint("timeout", section="http", default=30)
```

Make sure the query returns exactly one value column.

## 4) Full Chain With All Providers

```python
from configreader.configreader import ConfigReader

reader = ConfigReader(
    file="config.ini",
    db_url="sqlite:///settings.db",
    use_env=True,
    dictionary={"DEFAULT": {"workers": "2"}},
    providers=["env", "db", "ini", "dict"],
)

workers = reader.getint("workers", default=1)
```

Practical order:
1. quick overrides via env
2. central configuration from DB
3. local fallback from INI
4. final hard-coded fallback from dictionary