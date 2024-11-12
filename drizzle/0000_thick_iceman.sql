CREATE TABLE IF NOT EXISTS "user" (
	"id" uuid DEFAULT gen_random_uuid(),
	"name" text
);
