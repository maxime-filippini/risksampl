CREATE TYPE "public"."date_type" AS ENUM('current', 'history');--> statement-breakpoint
CREATE TABLE "dates" (
	"date" date PRIMARY KEY NOT NULL,
	"type" date_type NOT NULL
);
