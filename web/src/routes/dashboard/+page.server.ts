import { and, eq, gte, lte, max } from 'drizzle-orm';
import { db } from '$lib/server/db';
import { DatesTable, MeasurementsTable, portfolios } from '$lib/server/db/schema';
import type { PageServerLoad } from './$types';
import { getFirstDayOfYear } from '$lib/dates';

export const load: PageServerLoad = async () => {
	const ptfs = await db.select().from(portfolios);

	const currentDateResult = await db
		.select({ maxDate: max(DatesTable.date) })
		.from(DatesTable)
		.where(eq(DatesTable.type, 'current'));

	const currentDateStr = currentDateResult[0]?.maxDate;
	const currentDate = currentDateStr ? new Date(currentDateStr) : null;

	if (!currentDate || !currentDateStr) {
		throw new Error('No current date found in dates table');
	}

	const formatDate = (date: Date) =>
		new Intl.DateTimeFormat('en-CA', {
			timeZone: 'Europe/Luxembourg'
		}).format(date);

	const firstDayOfYear = getFirstDayOfYear();
	const firstDayOfYearStr = formatDate(firstDayOfYear);

	const dayMeasures = await db
		.select()
		.from(MeasurementsTable)
		.where(eq(MeasurementsTable.date, currentDateStr));

	const ytdPerf = await db
		.select()
		.from(MeasurementsTable)
		.where(
			and(
				eq(MeasurementsTable.measure, 'ptf_value'),
				gte(MeasurementsTable.date, firstDayOfYearStr),
				lte(MeasurementsTable.date, currentDateStr)
			)
		);

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

	return { ptfs, lastBusinessDayStr: currentDateStr, dayMeasures, ytdPerf, ytdPerformance };
};
