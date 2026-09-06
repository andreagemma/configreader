# Changelog

All notable changes to this project will be documented in this file.

## 0.1.4 - 2026-09-06

- Added `sections()` to return merged section names discovered across enabled providers (INI, DB, ENV, DICT).
- Added `variables(section)` to return merged variable names for a section across enabled providers.
- Kept `get_sections(section)` as a backward-compatible alias.
- Added tests for merged section and field discovery behavior.

## 0.1.0 - 2026-09-02

- Prepared environment
- Added complete project documentation in README and docs/ pages
