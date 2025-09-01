-- Rename holdings table to investments and modify structure
ALTER TABLE "holdings" RENAME TO "investments";

-- Add id column as primary key
ALTER TABLE "investments"
    ADD COLUMN "id" uuid DEFAULT gen_random_uuid();

ALTER TABLE "investments"
    ALTER COLUMN "id" SET NOT NULL;

-- Drop the old composite primary key (use IF EXISTS to handle missing constraint)
ALTER TABLE "investments"
    DROP CONSTRAINT IF EXISTS "holdings_pkey";

-- Add new primary key
ALTER TABLE "investments"
    ADD CONSTRAINT "investments_pkey" PRIMARY KEY ("id");

-- Rename as_of column to date
ALTER TABLE "investments" RENAME COLUMN "as_of" TO "date";

ALTER TABLE "investments"
    ALTER COLUMN "instrument_id" TYPE uuid
    USING "instrument_id"::uuid;

ALTER TABLE "investments"
    ALTER COLUMN "portfolio_id" TYPE uuid
    USING "portfolio_id"::uuid;

-- Update constraint names (use IF EXISTS to handle missing constraints)
ALTER TABLE "investments"
    DROP CONSTRAINT IF EXISTS "holdings_instrument_id_fkey";

ALTER TABLE "investments"
    DROP CONSTRAINT IF EXISTS "holdings_portfolio_id_fkey";

ALTER TABLE "investments"
    ADD CONSTRAINT "investments_instrument_id_fkey" FOREIGN KEY ("instrument_id") REFERENCES "public"."instruments"("id") ON DELETE CASCADE ON UPDATE NO action;

ALTER TABLE "investments"
    ADD CONSTRAINT "investments_portfolio_id_fkey" FOREIGN KEY ("portfolio_id") REFERENCES "public"."portfolios"("id") ON DELETE CASCADE ON UPDATE NO action;

-- Add indexes for better performance
CREATE INDEX "ix_investments_date" ON "investments" USING btree("date");

CREATE INDEX "ix_investments_portfolio" ON "investments" USING btree("portfolio_id" uuid_ops);

-- Update market_data table constraint name to avoid conflicts
ALTER TABLE "market_data"
    DROP CONSTRAINT IF EXISTS "pkey";

ALTER TABLE "market_data"
    ADD CONSTRAINT "market_data_pkey" PRIMARY KEY ("instrument_id", "date", "data_type");

