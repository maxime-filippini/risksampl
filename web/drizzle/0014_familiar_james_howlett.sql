CREATE TYPE "public"."measure_type" AS ENUM('value_at_risk', 'other');--> statement-breakpoint
CREATE TABLE "measures" (
	"id" varchar(200) PRIMARY KEY NOT NULL,
	"name" varchar(200),
	"type" "measure_type",
	"spec" jsonb
);
