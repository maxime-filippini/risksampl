import { db } from '$lib/server/db';
import { portfolios } from '$lib/server/db/schema';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const ptfs = await db.select().from(portfolios);

	return { ptfs };
};
