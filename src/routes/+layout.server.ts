import type { Session } from '@auth/sveltekit';
import type { LayoutServerLoad } from './$types';
import { db } from '@/server/db';
import { user } from '@/server/db/schema';
import { eq } from 'drizzle-orm';

export const load: LayoutServerLoad = async (event) => {
	const session: Session | null = await event.locals.auth();

	let user_;
	if (session == null || session.user == null || session.user.email == null) {
		user_ = null;
	} else {
		user_ = await db.select().from(user).where(eq(user.email, session.user.email)).limit(1);
		if (user_ !== null) {
			user_ = user_[0];
		}
	}

	return {
		session,
		user: user_
	};
};
