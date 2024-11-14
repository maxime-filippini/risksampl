import { db } from '@/server/db';
import type { PageServerLoad } from './$types';
import { portfolio, user } from '@/server/db/schema';
import { eq } from 'drizzle-orm';

export const load = (async () => {
	const query = db.select().from(portfolio).innerJoin(user, eq(portfolio.userId, user.id));

	const res = await query;

	return {
		portfolios: res,
		nPtf: res.length
	};
}) satisfies PageServerLoad;
