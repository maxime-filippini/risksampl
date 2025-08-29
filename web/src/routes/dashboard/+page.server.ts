import { db } from '$lib/server/db';
import { instruments } from '$lib/server/db/schema';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const out = await db.select().from(instruments);
	console.log(out);
};
