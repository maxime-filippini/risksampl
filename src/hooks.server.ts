import { sequence } from '@sveltejs/kit/hooks';
import { handle as authHandle } from './auth';
import { redirect, type Handle } from '@sveltejs/kit';

const handleProtectedRoutes: Handle = async ({ event, resolve }) => {
	const session = await event.locals.auth();

	if (event.url.pathname.startsWith('/admin')) {
		if (session?.user.role != 'admin') {
			redirect(303, '/');
		}
	}

	const result = await resolve(event);
	return result;
};

// We first have authjs add the session to the locals, and then use it to define
// whether users can access certain routes from their roles.
export const handle = sequence(authHandle, handleProtectedRoutes);
