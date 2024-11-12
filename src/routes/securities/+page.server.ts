import { db } from '@/server/db';
import type { PageServerLoad } from './$types';
import { security } from '@/server/db/schema';

export const load = (async () => {
	const res = await db.select().from(security);
	return {
		securities: res
	};
}) satisfies PageServerLoad;
