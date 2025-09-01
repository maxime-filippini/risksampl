import { db } from '$lib/server/db';
import {
	investments,
	instruments,
	MarketDataTable,
	portfolios,
	MeasuresTable
} from '$lib/server/db/schema';
import { eq, max, count, sql, min, isNotNull } from 'drizzle-orm';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const insts = await db
		.select({
			id: instruments.id,
			name: instruments.name,
			ticker: instruments.ticker,
			currency: instruments.currency,
			min_date: sql`market_data.min_date`,
			max_date: sql`market_data.max_date`
		})
		.from(instruments)
		.leftJoin(
			db
				.select({
					instrumentId: MarketDataTable.instrumentId,
					minDate: min(MarketDataTable.date).as('min_date'),
					maxDate: max(MarketDataTable.date).as('max_date')
				})
				.from(MarketDataTable)
				.groupBy(MarketDataTable.instrumentId)
				.as('market_data'),
			eq(instruments.id, sql`market_data.instrument_id`)
		);

	const ptfs = await db
		.select({
			id: portfolios.id,
			name: portfolios.name,
			currency: portfolios.currency,
			holdingsCount: count(
				sql`DISTINCT CASE WHEN investments.date = latest.max_as_of THEN investments.instrument_id END`
			)
		})
		.from(portfolios)
		.leftJoin(
			db
				.select({
					portfolioId: investments.portfolioId,
					maxAsOf: max(investments.date).as('max_as_of')
				})
				.from(investments)
				.groupBy(investments.portfolioId)
				.as('latest'),
			eq(portfolios.id, sql`latest.portfolio_id`)
		)
		.leftJoin(investments, eq(investments.portfolioId, portfolios.id))
		.groupBy(portfolios.id, sql`latest.max_as_of`);

	const all_measures = await db
		.selectDistinct({ measure: MeasuresTable.measure })
		.from(MeasuresTable)
		.where(isNotNull(MeasuresTable.measure));
	return { insts, ptfs, all_measures };
};
