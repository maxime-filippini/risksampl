import type { Actions, PageServerLoad } from './$types';
import { fail } from '@sveltejs/kit';
import * as z from 'zod';

const ContactSchema = z.object({
	email: z.email(),
	requestType: z.enum(['new-feature', 'doesnt-work', 'other-inquiry', 'keep-me-posted']),
	request: z.string()
});

export const load: PageServerLoad = async () => {
	return {};
};

export const actions: Actions = {
	contact: async ({ request }) => {
		const data = await request.formData();

		const formData = {
			email: data.get('email') as string,
			requestType: data.get('requestType') as string,
			request: data.get('request') as string
		};

		const result = ContactSchema.safeParse(formData);

		if (!result.success) {
			return fail(400, {
				success: false,
				errors: result.error.flatten(),
				data: formData
			});
		} else {
			return { success: true, errors: null };
		}
	}
};
