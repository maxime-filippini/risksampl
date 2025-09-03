ALTER TABLE "measures" RENAME TO "measurements";--> statement-breakpoint
ALTER TABLE "measurements" DROP CONSTRAINT "measures_portfolio_id_fkey";
--> statement-breakpoint
ALTER TABLE "measurements" ADD CONSTRAINT "measures_portfolio_id_fkey" FOREIGN KEY ("portfolio_id") REFERENCES "public"."portfolios"("id") ON DELETE cascade ON UPDATE no action;