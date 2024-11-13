import { db } from '@/server/db';
import type { PageServerLoad } from './$types';
import { security, securityType } from '@/server/db/schema';
import { eq } from 'drizzle-orm';

export const load = (async () => {
	const query = db
		.select({
			name: security.name,
			symbol: security.symbol,
			currency: security.currency,
			type: securityType.type
		})
		.from(security)
		.innerJoin(securityType, eq(security.typeId, securityType.id));

	const res = await query;
	return {
		securities: res,
		nSecurities: res.length
	};
}) satisfies PageServerLoad;
