import type { Session } from '@auth/sveltekit';
import type { PageServerLoad } from './$types';

export const load = (async (event) => {
	const session: Session | null = await event.locals.auth();
	return { session };
}) satisfies PageServerLoad;
