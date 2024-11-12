import { SvelteKitAuth, type User } from '@auth/sveltekit';
import Google from '@auth/sveltekit/providers/google';

import { db } from '@/server/db/index.js';
import * as schema from '$lib/server/db/schema';
import { eq } from 'drizzle-orm';

type NewUser = typeof schema.user.$inferInsert;

async function handleSignIn({ user }: { user: User }) {
	const usersInDb = await db.select().from(schema.user);
	console.log('New user: ', user);
	console.log('Users in DB: ', usersInDb);

	if (user.id == undefined) {
		return false;
	}

	const in_db = await db
		.select()
		.from(schema.user)
		.where(eq(schema.user.oAuthId, user.id))
		.limit(1);

	if (in_db.length == 0) {
		console.log('!!!! NEW USER');

		const newUser: NewUser = {
			name: user.name,
			email: user.email,
			oAuthId: user.id
		};

		await db.insert(schema.user).values(newUser);
		console.log('Inserted user!');
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
