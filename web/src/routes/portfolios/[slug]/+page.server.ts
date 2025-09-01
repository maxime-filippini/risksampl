import { asc, eq } from 'drizzle-orm';
import { db } from '$lib/server/db';
import { instruments, investments, portfolios } from '$lib/server/db/schema';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ params }) => {
	const investments_ = await db
		.select({
			date: investments.date,
			instrument: instruments.name,
			quantity: investments.quantity
		})
		.from(investments)
		.where(eq(investments.portfolioId, params.slug))
		.leftJoin(instruments, eq(investments.instrumentId, instruments.id))
		.orderBy(asc(investments.date));

	const ptf = await db.select().from(portfolios).where(eq(portfolios.id, params.slug)).limit(1);

	return { slug: params.slug, investments: investments_, ptf: ptf[0] ?? null };
};
