import { db } from '$lib/server/db';
import { MeasuresTable } from '$lib/server/db/schema';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async () => {
	const measures = await db.select().from(MeasuresTable).orderBy(MeasuresTable.id);

	return { measures };
};
