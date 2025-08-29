import { db } from '$lib/server/db';
import { holdings, instruments, portfolios } from '$lib/server/db/schema';
import { eq, max, count, sql } from 'drizzle-orm';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const insts = await db.select().from(instruments);
	const ptfs = await db
		.select({
			id: portfolios.id,
			name: portfolios.name,
			currency: portfolios.currency,
			holdingsCount: count(
				sql`DISTINCT CASE WHEN holdings.as_of = latest.max_as_of THEN holdings.instrument_id END`
			)
		})
		.from(portfolios)
		.leftJoin(
			db
				.select({
					portfolioId: holdings.portfolioId,
					maxAsOf: max(holdings.asOf).as('max_as_of')
				})
				.from(holdings)
				.groupBy(holdings.portfolioId)
				.as('latest'),
			eq(portfolios.id, sql`latest.portfolio_id`)
		)
		.leftJoin(holdings, eq(holdings.portfolioId, portfolios.id))
		.groupBy(portfolios.id, sql`latest.max_as_of`);
	return { insts, ptfs };
};
