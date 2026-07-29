CREATE TYPE "public"."market_data_ingestion_run_status" AS ENUM('running', 'promoted', 'no_change', 'failed');--> statement-breakpoint
CREATE TABLE "canonical_market_data_state" (
	"singleton" boolean PRIMARY KEY DEFAULT true NOT NULL,
	"current_snapshot_manifest_key" text,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "canonical_market_data_state_singleton" CHECK ("canonical_market_data_state"."singleton")
);
--> statement-breakpoint
CREATE TABLE "market_data_ingestion_runs" (
	"logical_run_id" varchar(255) PRIMARY KEY NOT NULL,
	"status" "market_data_ingestion_run_status" NOT NULL,
	"started_at" timestamp with time zone NOT NULL,
	"finished_at" timestamp with time zone,
	"base_snapshot_manifest_key" text NOT NULL,
	"promoted_snapshot_manifest_key" text,
	"raw_response_manifest_keys" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"instrument_status" jsonb DEFAULT '[]'::jsonb NOT NULL,
	"error" text,
	CONSTRAINT "market_data_ingestion_runs_terminal_state" CHECK ((
				("market_data_ingestion_runs"."status" = 'running'
					AND "market_data_ingestion_runs"."finished_at" IS NULL
					AND "market_data_ingestion_runs"."promoted_snapshot_manifest_key" IS NULL
					AND "market_data_ingestion_runs"."error" IS NULL)
				OR
				("market_data_ingestion_runs"."status" = 'promoted'
					AND "market_data_ingestion_runs"."finished_at" IS NOT NULL
					AND "market_data_ingestion_runs"."promoted_snapshot_manifest_key" IS NOT NULL
					AND "market_data_ingestion_runs"."error" IS NULL)
				OR
				("market_data_ingestion_runs"."status" = 'no_change'
					AND "market_data_ingestion_runs"."finished_at" IS NOT NULL
					AND "market_data_ingestion_runs"."promoted_snapshot_manifest_key" IS NULL
					AND "market_data_ingestion_runs"."error" IS NULL)
				OR
				("market_data_ingestion_runs"."status" = 'failed'
					AND "market_data_ingestion_runs"."finished_at" IS NOT NULL
					AND "market_data_ingestion_runs"."promoted_snapshot_manifest_key" IS NULL
					AND "market_data_ingestion_runs"."error" IS NOT NULL)
			))
);
--> statement-breakpoint
CREATE INDEX "ix_market_data_ingestion_runs_status_started" ON "market_data_ingestion_runs" USING btree ("status","started_at");--> statement-breakpoint
CREATE UNIQUE INDEX "ux_market_data_ingestion_runs_single_running" ON "market_data_ingestion_runs" USING btree ("status") WHERE "market_data_ingestion_runs"."status" = 'running';