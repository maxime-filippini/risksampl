import { db } from '@/server/db';
import type { PageServerLoad } from './$types';
import { portfolio, user } from '@/server/db/schema';
import { eq } from 'drizzle-orm';
import { env } from '$env/dynamic/private';

export const load = (async () => {
	const queryCustomPtfs = db
		.select()
		.from(portfolio)
		.innerJoin(user, eq(portfolio.userId, user.id));
	const queryGlobalPtfs = db
		.select()
		.from(portfolio)
		.innerJoin(user, eq(portfolio.userId, env.APP_GLOBAL_USER_ID));

	const resCustom = await queryCustomPtfs;
	const resGlobal = await queryGlobalPtfs;
	return {
		customPortfolios: resCustom,
		nCustomPortfolios: resCustom.length,
		globalPortfolios: resGlobal,
		nGlobalPortfolios: resGlobal.length
	};
}) satisfies PageServerLoad;
