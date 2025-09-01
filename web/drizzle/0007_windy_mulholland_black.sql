CREATE TABLE "measures" (
	"portfolio_id" uuid NOT NULL,
	"date" date NOT NULL,
	"measure" varchar(50),
	"value" numeric,
	CONSTRAINT "measures_pkey" PRIMARY KEY("portfolio_id","date","measure")
);
--> statement-breakpoint
ALTER TABLE "measures" ADD CONSTRAINT "measures_portfolio_id_fkey" FOREIGN KEY ("portfolio_id") REFERENCES "public"."portfolios"("id") ON DELETE cascade ON UPDATE no action;