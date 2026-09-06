# Changelog

All notable changes to this project will be documented in this file.

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
