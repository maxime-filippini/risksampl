import { db } from '$lib/server/db';
import { instruments, portfolios } from '$lib/server/db/schema';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const insts = await db.select().from(instruments);
	const ptfs = await db.select().from(portfolios);
	return { insts, ptfs };
};
