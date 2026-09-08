# Changelog

All notable changes to this project will be documented in this file.

## 0.2.2 - 2026-09-08
 - Release Dummy
## 0.2.1 - 2026-09-08
 - Release Dummy
## 0.2.0 - 2026-09-08

- Added `cached: bool = True` to `ConfigReader` constructor.
- Added startup cache build for enabled providers and cache-based reads in:
	- `get(...)`
	- `items()`
	- `sections()`
	- `variables(section)`
- Added `refresh(on_cache_exists=...)` to reload providers and rebuild cache.
- Added `cache(on_cache_exists=...)` to build cache on demand.
- Updated `copy(...)` to support `copy_cache: bool = False` and cache copy on demand.
- Added `on_cache_exists` policy (`"ignore" | "raise" | "warning"`) to `refresh`, `cache`, and `copy(copy_cache=True)` when cache is missing.
- Removed `get_sections(section)` alias.

## 0.1.5 - 2026-09-06

- Added third-party compliance artifacts derived from dependencies declared in `pyproject.toml`:
	- `licenses/third_party/packages/<package>/LICENSE`
	- `licenses/third_party/summary.tsv`
	- `THIRD_PARTY_NOTICES.md`
- Updated `MANIFEST.in` to include third-party notices and archived license files in source distributions.
- Added repository Copilot instructions in `.github/copilot-instructions.md` aligned to project structure and quality checks.

## 0.1.4 - 2026-09-06

- Added `sections()` to return merged section names discovered across enabled providers (INI, DB, ENV, DICT).
- Added `variables(section)` to return merged variable names for a section across enabled providers.
- Kept `get_sections(section)` as a backward-compatible alias.
- Added tests for merged section and field discovery behavior.

## 0.1.0 - 2026-09-02

- Prepared environment
- Added complete project documentation in README and docs/ pages
