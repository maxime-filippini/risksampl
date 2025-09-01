CREATE TABLE "ptf_comp" (
	"date" date NOT NULL,
	"portfolio_id" uuid NOT NULL,
	"instrument_id" uuid NOT NULL,
	"quantity" numeric(20, 8) NOT NULL,
	"value" numeric(20, 8) NOT NULL,
	CONSTRAINT "ptf_comp_pkey" PRIMARY KEY("instrument_id","portfolio_id","date")
);
--> statement-breakpoint
ALTER TABLE "ptf_comp" ADD CONSTRAINT "ptf_comp_portfolio_id_fkey" FOREIGN KEY ("portfolio_id") REFERENCES "public"."portfolios"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "ptf_comp" ADD CONSTRAINT "ptf_comp_instrument_id_fkey" FOREIGN KEY ("instrument_id") REFERENCES "public"."instruments"("id") ON DELETE cascade ON UPDATE no action;