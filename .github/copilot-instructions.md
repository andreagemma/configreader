# Copilot Instructions for configreader

## Project Description

configreader is a typed Python library to resolve configuration values from multiple providers (INI, DB via SQLAlchemy, environment variables, dictionaries) with explicit precedence.

## Scope

These instructions apply to the entire repository.

## Project Context

- This is a Python package with sources under src/configreader.
- Keep compatibility with the existing public API and behavior.
- Preserve provider ordering semantics and fallback behavior.

## Development Rules

- Prefer small, targeted changes.
- Keep code typed and add type annotations on public functions and classes.
- Do not break public APIs unless explicitly requested.
- Add or update tests under tests/ for behavioral changes.
- Maintain consistent style with the current project.
- Avoid heavy new dependencies unless clearly justified.

## Quality Checks

Before finalizing changes, run:

- pytest -q

## Verification and Alignment

- Keep CHANGELOG.md updated when behavior or interfaces change.
- Keep README.md and docs/ content aligned with code changes.
- Verify dependencies are correctly declared in pyproject.toml.
- Keep MANIFEST.in updated.

## Third-Party Licensing Workflow

Based on dependencies declared in pyproject.toml:

- Archive third-party licenses under licenses/third_party/packages/<package>/.
- Save at least one LICENSE file for each package.
- Save COPYING too when upstream provides it.
- Keep licenses/third_party/summary.tsv updated with columns:
  package, version, license_file, source_url.
- Keep THIRD_PARTY_NOTICES.md updated.
- Ensure MANIFEST.in includes these artifacts.

## Safety

- Do not run destructive git history operations.
- Ask for clarification before broad refactors when requirements are ambiguous.
