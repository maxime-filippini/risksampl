import { and, eq, gte } from 'drizzle-orm';
import { db } from '$lib/server/db';
import { MeasuresTable, portfolios } from '$lib/server/db/schema';
import type { PageServerLoad } from './$types';
import { getBusinessDayBefore, getFirstDayOfYear } from '$lib/dates';

export const load: PageServerLoad = async () => {
	const ptfs = await db.select().from(portfolios);

	const today = new Date();

	const formatDate = (date: Date) =>
		new Intl.DateTimeFormat('en-CA', {
			timeZone: 'Europe/Luxembourg'
		}).format(date);

	const lastBusinessDay = getBusinessDayBefore(today);
	const lastBusinessDayStr = formatDate(lastBusinessDay);

	const firstDayOfYear = getFirstDayOfYear();
	const firstDayOfYearStr = formatDate(firstDayOfYear);

	const dayMeasures = await db
		.select()
		.from(MeasuresTable)
		.where(eq(MeasuresTable.date, lastBusinessDayStr));

	const ytdPerf = await db
		.select()
		.from(MeasuresTable)
		.where(and(eq(MeasuresTable.measure, 'ptf_value'), gte(MeasuresTable.date, firstDayOfYearStr)));

	const ytdPerfByPortfolio = ytdPerf.reduce(
		(acc, record) => {
			const { portfolioId, date, value } = record;
			if (!acc[portfolioId]) {
				acc[portfolioId] = {};
			}
			acc[portfolioId][date] = parseFloat(value || '0');
			return acc;
		},
		{} as Record<string, Record<string, number>>
	);

	const ytdPerformance = Object.entries(ytdPerfByPortfolio).map(([portfolioId, values]) => {
		const dates = Object.keys(values).sort();
		const startValue = values[dates[0]];
		const endValue = values[dates[dates.length - 1]];
		const performance = ((endValue - startValue) / startValue) * 100;

		return {
			portfolioId,
			startValue,
			endValue,
			performance: parseFloat(performance.toFixed(2))
		};
	});

	return { ptfs, lastBusinessDayStr, dayMeasures, ytdPerf, ytdPerformance };
};
