import { db } from '$lib/server/db';
import { instruments } from '$lib/server/db/schema';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const insts = await db.select().from(instruments);
	const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Luxembourg' }).format(
		new Date()
	);
	return { insts, today };
};
