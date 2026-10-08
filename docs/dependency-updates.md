# Dependency update guide

Rules for upgrading dependencies in this project. Version-agnostic: follow the
process regardless of which packages `poetry show --outdated` reports.

## Process

1. `poetry show --outdated` — list what is behind (also check
   `poetry update --lock --dry-run` for transitive-only moves).
2. Classify each package (below) and read its changelog if the bump is MAJOR —
   find every entry marked **BREAKING**.
3. One branch, **one commit per group**: 🟢 then 🟡 then 🔴, each 🔴 on its own.
4. After every commit, run the gate (below). Red → fix or revert that commit;
   never stack a broken upgrade on another.
5. Commit `pyproject.toml` **and** `poetry.lock` together, always (plus
   `requirements.txt` / `requirements/*.txt` if regenerated).

## Classification

| Group | Rule |
|-------|------|
| 🟢 low | Patch or minor bump, no Django/DRF involvement |
| 🟡 medium | Major, but confined (telemetry, test-only tooling, docs, one feature) |
| 🔴 high | Django, DRF, or core toolchain major (affects the app or the test pipeline) |
| ⛔ defer | Major not yet proven in the ecosystem (e.g. Django 6, Python 3.13) — skip until the Django plugin ecosystem supports it |

## Coupled packages (same commit)

- `django` with `django-stubs` (dev)
- `djangorestframework` with `djangorestframework-stubs` (dev)
- `drf-spectacular` with the Django/DRF major it targets
- `cryptography` with `pyopenssl`
- `redis` with its `hiredis` extra

Django 5.x → 6.x moves every `django-*` plugin: check support in
`django-tenants`, `django-smart-ratelimit`, `django-weasyprint`,
`djangosaml2`, `django-cas-sso` first — if any lags, the whole move is ⛔.

## Commands

```bash
poetry show --outdated              # what's behind
poetry update <pkg>                 # update within the existing range
# to leave the range: edit the range in pyproject.toml first, then
poetry update <pkg>
poetry update --lock                # transitive deps only, no range change
poetry show <pkg>                   # verify installed version
```

## Gate — run after every commit, in this order

Run from a bare shell with `poetry run` (or activate the venv with
`poetry shell` first; the venv must have the dev group installed, i.e. a
plain `poetry install`):

```bash
poetry run ruff check . && poetry run ruff format --check .
poetry run tox -e py312             # full test suite with coverage
poetry run tox -e safety            # security scan (needs SAFETY_API_KEY)
```

Then a manual smoke test (`docker-compose up`):
login (CAS / SAML / JWT), one main workflow, a PDF export, an admin page,
dev toolbar loads (dev settings), no warnings/errors in the server logs.

Green → commit and continue. Red → read the changelog and fix; failing that,
`git revert <commit>` and park the package (note it in the PR).

## Rollback

Unpushed: `git reset --hard <commit-before>`. Pushed/merged: `git revert` per
group commit. Production issue: `git bisect` across the round commits, then
rebuild the image from the green commit.

## Changelogs

PyPI: append `changelog` at `pypi.org/project/<pkg>/` history, or the GitHub
repo: append `/releases`.

Runtime: `django` + plugins — django/django, the respective plugin repos ·
`djangorestframework` Encode/django-rest-framework ·
`drf-spectacular` tfranzel/drf-spectacular ·
`sentry-sdk` getsentry/sentry-python ·
`pyopenssl` pyopenssl/pyopenssl · `cryptography` pyca/cryptography ·
`redis` redis/redis-py ·
`pydantic` pydantic/pydantic ·
`psycopg` psycopg/psycopg ·
`django-smart-ratelimit` jnns/django-smart-ratelimit ·
`djangosaml2` IdentityPython/django-saml2 ·
`django-cas-sso` django-cas/django-cas-sso

Dev: `ruff` + `pycodestyle` astral-sh/ruff, PyCQA/pycodestyle ·
`pylint` pylint-dev/pylint ·
`django-stubs` + `djangorestframework-stubs` django-stubs ·
`factory-boy` factoryboy/factory_boy ·
`coverage` ned/coveragepy ·
`pre-commit` pre-commit/pre-commit ·
`sphinx` sphinx-doc/sphinx ·
`tox` tox-dev/tox
