import type { Session } from '@auth/sveltekit';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async (event) => {
	const session: Session | null = await event.locals.auth();
	return {
		session,
		user: session?.user
	};
};
