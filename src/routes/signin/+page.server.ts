import type { RequestEvent } from '@sveltejs/kit';
import { signIn as si } from '../../auth';
import type { Actions } from './$types';

async function signIn(e: RequestEvent<Partial<Record<string, string>>, string | null>) {
	const resp = await si(e);
	return resp;
}

export const actions: Actions = {
	default: signIn
};
