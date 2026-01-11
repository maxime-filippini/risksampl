# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Risksampl is a web application for visualizing risk levels in sample investment portfolios. It provides risk metrics including Value at Risk (VaR), volatility, and performance tracking.

**Architecture:** Monorepo with three main components:
- `/web` - SvelteKit frontend application
- `/worker` - Python FastAPI backend worker service
- `/db` - PostgreSQL database (Docker)

## Common Development Commands

### Root-level commands (from repository root)

**Web application:**
```bash
bun run web:dev        # Start SvelteKit dev server on 0.0.0.0:5173
bun run web:setup      # Install frontend dependencies with Bun
```

**Worker service:**
```bash
bun run worker:dev     # Start FastAPI worker on port 8000
bun run worker:setup   # Install Python dependencies with UV
```

**Database:**
```bash
bun run db:start       # Launch PostgreSQL container
bun run db:push        # Push schema changes to database
bun run db:generate    # Generate migration files
bun run db:migrate     # Run migrations
bun run db:studio      # Open Drizzle Studio (visual DB editor)
```

### Frontend-specific (from web/ directory)

For running frontend commands, always use `bun`, never `npm`.

```bash
bun run check          # Type checking with svelte-check
bun run lint           # Run ESLint and Prettier
bun run format         # Format code with Prettier
bun run gen:api        # Generate TypeScript types from worker OpenAPI spec (requires worker running on port 8000)
bun run build          # Build for production
```

### Worker-specific (from worker/ directory)

```bash
uv run pytest          # Run Python tests
```

## Architecture Patterns

### Distributed Worker with Leader Lock

The worker uses PostgreSQL advisory locks to ensure only one instance runs scheduled jobs, preventing duplicate job execution in multi-instance deployments.

- Leader lock acquired in `main.py` lifespan using `pg_try_advisory_lock()`
- Only the leader instance schedules and runs jobs
- Lock held for the lifetime of the process

### Type-Safe API Integration

The frontend and backend maintain type safety through OpenAPI:

1. Worker exposes OpenAPI specification at `/openapi.json`
2. Run `bun run gen:api` (from web/ directory) to generate TypeScript types
3. Generated types saved to `web/src/lib/types/api.ts`
4. Frontend uses `openapi-fetch` for type-safe API calls

**Important:** Regenerate types after any worker API changes.

### Data Flow

1. APScheduler triggers `daily_run()` at 8:00 AM (weekdays only)
2. Worker loads portfolio data from database
3. Fetches market data from MarketStack API
4. Calculates VaR, volatility, and other risk metrics
5. Stores measurements in database
6. SvelteKit routes query database via Drizzle ORM
7. Frontend renders charts with ECharts

### Database Schema Management

- Schema defined in TypeScript: `web/src/lib/server/db/schema.ts`
- Drizzle ORM for type-safe database access from frontend
- Drizzle Kit for migrations
- Core tables: instruments, portfolios, investments, market_data, measurements, var_models, dates

**Workflow:**
1. Modify schema in `web/src/lib/server/db/schema.ts`
2. Run `bun run db:generate` to create migration files
3. Run `bun run db:push` to apply changes to database

## Key Technologies

**Frontend:**
- SvelteKit 2.x with TypeScript
- Vite 7.x build tool
- Tailwind CSS 4.x + DaisyUI component library
- ECharts 6.x for data visualization
- Drizzle ORM for database queries
- Bun package manager

**Backend:**
- Python 3.13+ with FastAPI
- APScheduler for cron job scheduling
- Pandas/Polars for data processing
- SQLAlchemy 2.0+ ORM
- UV package manager
- pytest for testing

**Database:**
- PostgreSQL 17 in Docker
- Drizzle Kit for schema migrations

## Important Patterns

### VaR Model Specifications

VaR (Value at Risk) models are stored as JSON in the `var_models` table, supporting multiple calculation methods:
- Historical simulation
- Parametric (normal distribution)
- EWMA (Exponentially Weighted Moving Average)

Model specs define lookback periods, confidence levels, and decay factors. Core calculation logic is in `worker/src/worker/var.py`.

### Database Access

- **Frontend:** Direct Drizzle ORM queries in `+page.server.ts` files
- **Worker:** SQLAlchemy for database operations
- Connection URLs automatically converted from `postgres://` to `postgresql://` in worker settings

### Scheduled Jobs

The worker runs a daily job with these characteristics:
- **Schedule:** 8:00 AM daily (cron trigger)
- **Weekdays only:** Skips weekends in `do_daily_run()`
- **Idempotent:** Can be re-run for the same date safely
- **Job persistence:** State stored in database via SQLAlchemyJobStore
- **Testing mode:** Uses `IntervalTrigger(seconds=10)` when `TESTING=True`

### Environment Configuration

Required `.env` file variables:
- `DATABASE_URL` - PostgreSQL connection string
- `MARKETSTACK_API_KEY` - API key for market data
- `TESTING` - Boolean flag for testing mode (optional)
