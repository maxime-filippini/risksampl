import { db } from '@/server/db/index.js';
import * as schema from '$lib/server/db/schema';

export async function load() {
	const models = await db.select().from(schema.user);
	return { models: models };
}
