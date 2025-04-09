# Ecobalyse Backoffice

## Requirements

- [uv](https://docs.astral.sh/uv/) for Python (it will manage the Python install for you)
- PostgreSQL if you don’t want to use the default SQLite database

## Install Python dependencies

```bash
uv sync
```

## Migrate the database to the latest version

```bash
uv run backend database upgrade --no-prompt
```

## Run the dev server

```bash
uv run backend run --debug --reload
```

Calling `http://localhost:8000/health` should give you the following JSON:

```json
{
    "database_status":"online",
    "app":"app",
    "version":"0.0.1"
}
```

## OpenAPI documentation

[http://localhost:8000/schema](http://localhost:8000/schema)
