import type { Session } from '@auth/sveltekit';
import type { PageServerLoad } from './$types';
import { redirect } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';

export const load = (async (event) => {
	const session: Session | null = await event.locals.auth();

	if (session?.user?.id !== env.APP_ADMIN_USER_ID) {
		console.log('Unauthorized.');
		redirect(302, '/');
	}

	return { session };
}) satisfies PageServerLoad;
