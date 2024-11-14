import type { PageServerLoad } from './$types';

export const load = (async () => {
	return {
		portfolios: [],
		nPtf: 0
	};
}) satisfies PageServerLoad;
