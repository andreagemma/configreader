# Overview

config_reader is a small utility library that centralizes configuration lookup across multiple sources.

Core goals:
- automatic fallback between providers
- configurable provider precedence
- uniform API for raw and typed values

## Supported Sources

- ini: local INI file
- db: SQL query through SQLAlchemy
- env: environment variables
- dict: in-memory Python dictionary

## Resolution Flow

1. a get* method is called
2. providers are checked in the configured order
3. the first non-None value is returned
4. if no value is found, default is returned

## When To Use

- applications with environment-based overrides
- services with central DB settings and local fallback
- tests where values are injected from a dictionary

## When Not To Use

- complex schema validation for configuration payloads
- advanced secret management with rotation policies

In these scenarios, pair this library with dedicated validators or secret management tools.