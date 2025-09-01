CREATE TABLE "ptf_values"(
    "date" date NOT NULL,
    "portfolio_id" uuid NOT NULL,
    "value" numeric(20, 8) NOT NULL,
    CONSTRAINT "ptf_values_pkey" PRIMARY KEY ("portfolio_id", "date")
);

--> statement-breakpoint
ALTER TABLE "ptf_values"
    ADD CONSTRAINT "portfolio_id_fkey" FOREIGN KEY ("portfolio_id") REFERENCES "public"."portfolios"("id") ON DELETE CASCADE ON UPDATE NO action;

