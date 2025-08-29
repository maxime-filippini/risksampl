-- Current sql file was generated after introspecting the database
-- If you want to run this migration please uncomment this code before executing migrations
CREATE TABLE "alembic_version"(
    "version_num" varchar(32) PRIMARY KEY NOT NULL
);

CREATE TABLE "instruments"(
    "id" uuid PRIMARY KEY NOT NULL,
    "name" varchar(255) NOT NULL,
    "ticker" varchar(10) NOT NULL,
    "currency" varchar(3) NOT NULL,
    CONSTRAINT "instruments_name_key" UNIQUE ("name")
);

CREATE TABLE "portfolios"(
    "id" uuid PRIMARY KEY NOT NULL,
    "name" varchar(100) NOT NULL,
    "currency" varchar(3) NOT NULL,
    CONSTRAINT "portfolios_name_key" UNIQUE ("name")
);

CREATE TABLE "holdings"(
    "as_of" date NOT NULL,
    "portfolio_id" uuid NOT NULL,
    "instrument_id" uuid NOT NULL,
    "quantity" numeric(20, 8) NOT NULL,
    CONSTRAINT "holdings_pkey" PRIMARY KEY ("as_of", "portfolio_id", "instrument_id")
);

ALTER TABLE "holdings"
    ADD CONSTRAINT "holdings_instrument_id_fkey" FOREIGN KEY ("instrument_id") REFERENCES "public"."instruments"("id") ON DELETE CASCADE ON UPDATE NO action;

--> statement-breakpoint
ALTER TABLE "holdings"
    ADD CONSTRAINT "holdings_portfolio_id_fkey" FOREIGN KEY ("portfolio_id") REFERENCES "public"."portfolios"("id") ON DELETE CASCADE ON UPDATE NO action;

--> statement-breakpoint
CREATE INDEX "ix_instruments_id" ON "instruments" USING btree("id" uuid_ops);

--> statement-breakpoint
CREATE UNIQUE INDEX "ix_instruments_ticker" ON "instruments" USING btree("ticker" text_ops);

--> statement-breakpoint
CREATE INDEX "ix_portfolios_id" ON "portfolios" USING btree("id" uuid_ops);

