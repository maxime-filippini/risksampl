CREATE TABLE "market_data" (
	"instrument_id" uuid NOT NULL,
	"date" date NOT NULL,
	"data_type" varchar(50),
	"value" numeric,
	CONSTRAINT "pkey" PRIMARY KEY("instrument_id","date","data_type")
);
--> statement-breakpoint
CREATE TABLE "requests" (
	"id" uuid PRIMARY KEY NOT NULL,
	"email" varchar(255) NOT NULL,
	"request" varchar(10000) NOT NULL
);
--> statement-breakpoint
ALTER TABLE "market_data" ADD CONSTRAINT "instrument_id_fkey" FOREIGN KEY ("instrument_id") REFERENCES "public"."instruments"("id") ON DELETE cascade ON UPDATE no action;