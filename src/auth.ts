import { eq } from 'drizzle-orm';
import { SvelteKitAuth, type DefaultSession } from '@auth/sveltekit';
import Google from '@auth/sveltekit/providers/google';

import { db } from '@/server/db/index.js';
import { DrizzleAdapter } from '@auth/drizzle-adapter';
import { sessions, users } from '@/server/db/schema';

declare module '@auth/sveltekit' {
	interface Session {
		user: {
			role: string;
		} & DefaultSession['user'];
	}
}

export const { handle, signIn, signOut } = SvelteKitAuth({
	providers: [
		Google({
			allowDangerousEmailAccountLinking: true, // Should not need that, but see: https://github.com/nextauthjs/next-auth/issues/11261
			profile: (profile) => {
				return {
					role: 'user',
					...profile
				};
			}
		})
	],

	adapter: DrizzleAdapter(db),
	session: {
		strategy: 'database'
	},
	callbacks: {
		async session({ session }) {
			// For some reason, I cannot get the role from the user passed to
			// this callback, and I have to fetch it myself
			const user_ = await db
				.select({
					role: users.role
				})
				.from(users)
				.leftJoin(sessions, eq(users.id, sessions.userId))
				.where(eq(sessions.sessionToken, session.sessionToken))
				.limit(1);

			if (user_.length != 1) {
				throw new Error('should not happen');
			}

			session.user.role = user_[0].role;
			return session;
		}
	},
	trustHost: true
});
