import { redirect } from '@sveltejs/kit';

export function load() {
	console.log('hey there');
	redirect(302, '/');
}
