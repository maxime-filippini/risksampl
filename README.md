# Risksampl

A web application used to get a view of risk levels based on sample portfolio data.

## VaR Labs beta baseline

This repository is preserved as the legacy Risksampl reference while VaR Labs beta work begins from a verified baseline. See [the baseline notes](docs/var-labs-beta-baseline.md) for the scope, preserved behavior, and verification commands.

## Repository structure

- `/web` contains the web application, built using SvelteKit.
- `/worker` is a Python application that schedules data retrieval and updates the database.


## Processes

#### Launch the application

```bash
bun run dev
```

#### Start local database container

```bash
bun run db:start
```

#### Get production data to dev environment

```bash
ssh <user>@<server>
docker exec -t <container_id> pg_dump -U <db_user> > path/to/dump

# > Exit shell

scp <user>@<server>:path/to/dump local/path/to_dump
docker exec -i <local_db_container_id> psql -U user -d risksampl < local/path/to_dump
```
