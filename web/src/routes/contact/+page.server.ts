import type { Actions, PageServerLoad } from './$types';
import * as z from 'zod';

const ContactSchema = z.object({
	email: z.email(),
	requestType: z.enum(['new-feature', 'doesnt-work', 'other-inquiry']),
	request: z.string().nonempty()
});

export const load: PageServerLoad = async () => {
	return {};
};

export const actions: Actions = {
	contact: async ({ request }) => {
		const data = await request.formData();

		const result = ContactSchema.safeParse({
			email: data.get('email'),
			requestType: data.get('requestType'),
			request: data.get('request')
		});

		if (!result.success) {
			return { success: false, errors: z.flattenError(result.error) };
		} else {
			return { success: true, errors: null };
		}
	}
};
