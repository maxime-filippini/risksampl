CREATE TABLE IF NOT EXISTS "portfolio" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"name" text
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "securities_to_portfolios" (
	"securityId" uuid NOT NULL,
	"portfolioId" uuid NOT NULL,
	CONSTRAINT "securities_to_portfolios_securityId_portfolioId_pk" PRIMARY KEY("securityId","portfolioId")
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "security" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"name" text,
	"symbol" text
);
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "securities_to_portfolios" ADD CONSTRAINT "securities_to_portfolios_securityId_security_id_fk" FOREIGN KEY ("securityId") REFERENCES "public"."security"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "securities_to_portfolios" ADD CONSTRAINT "securities_to_portfolios_portfolioId_portfolio_id_fk" FOREIGN KEY ("portfolioId") REFERENCES "public"."portfolio"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
