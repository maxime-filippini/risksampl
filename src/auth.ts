import { SvelteKitAuth, type User } from '@auth/sveltekit';
import Google from '@auth/sveltekit/providers/google';

import { db } from '@/server/db/index.js';
import * as schema from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';

type NewUser = typeof schema.user.$inferInsert;

async function handleSignIn({ user }: { user: User }) {
	if (user.email == undefined || user.id == undefined || user.name == undefined) {
		return false;
	}

	const in_db = await db
		.select()
		.from(schema.user)
		.where(eq(schema.user.email, user.email))
		.limit(1);

	if (in_db.length == 0) {
		const newUser: NewUser = {
			name: user.name,
			email: user.email,
			oAuthId: user.id
		};

		await db.insert(schema.user).values(newUser);
	}

	return true;
}

export const { handle, signIn, signOut } = SvelteKitAuth({
	providers: [Google],
	callbacks: {
		signIn: handleSignIn
	},
	trustHost: true
});
