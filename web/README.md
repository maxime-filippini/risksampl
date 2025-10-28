# Risksampl


## To launch locally

## Set up the database

Start by launching the local database via Docker.

```console
bun run db:start
```

### Optional: Restore from a backup.

On the server:

```console
docker exec -it <db-container> pg_dump -U <user> -Fc <database> > backup.dump
docker cp <db-container>:backup.dump /tmp/backup.dump
```

On your machine

```console
scp <machine>:/tmp/backup.dump .
docker exec -it <local-db-container> pg_restore -U <user> -d <database> /tmp/backup.dump
```

### Apply migrations

Apply the migrations that may be missing

```console
bun run db:migrate
```
