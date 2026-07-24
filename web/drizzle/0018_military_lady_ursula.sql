ALTER TABLE "instruments" ADD COLUMN "provider_symbol" varchar(32);--> statement-breakpoint
ALTER TABLE "instruments" ADD COLUMN "exchange_code" varchar(16);--> statement-breakpoint
ALTER TABLE "instruments" ADD COLUMN "enabled" boolean DEFAULT false NOT NULL;--> statement-breakpoint
ALTER TABLE "instruments" ADD COLUMN "catch_up_required" boolean DEFAULT false NOT NULL;--> statement-breakpoint
ALTER TABLE "instruments" ADD COLUMN "first_validated_observation_date" date;--> statement-breakpoint
ALTER TABLE "instruments" ADD COLUMN "latest_validated_observation_date" date;--> statement-breakpoint
CREATE UNIQUE INDEX "ix_instruments_provider_identity" ON "instruments" USING btree ("provider_symbol","exchange_code");--> statement-breakpoint
ALTER TABLE "instruments" ADD CONSTRAINT "instruments_provider_identity_complete" CHECK (("instruments"."provider_symbol" IS NULL) = ("instruments"."exchange_code" IS NULL));--> statement-breakpoint
ALTER TABLE "instruments" ADD CONSTRAINT "instruments_validated_coverage_complete" CHECK ((("instruments"."first_validated_observation_date" IS NULL) = ("instruments"."latest_validated_observation_date" IS NULL))
				AND ("instruments"."first_validated_observation_date" IS NULL OR "instruments"."first_validated_observation_date" <= "instruments"."latest_validated_observation_date"));--> statement-breakpoint
ALTER TABLE "instruments" ADD CONSTRAINT "instruments_enabled_state_complete" CHECK (NOT "instruments"."enabled" OR (
				"instruments"."provider_symbol" IS NOT NULL
				AND "instruments"."exchange_code" IS NOT NULL
				AND "instruments"."first_validated_observation_date" IS NOT NULL
				AND "instruments"."latest_validated_observation_date" IS NOT NULL
				AND NOT "instruments"."catch_up_required"
			));