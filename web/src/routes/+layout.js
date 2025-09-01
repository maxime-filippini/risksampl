import posthog from 'posthog-js';
import { browser } from '$app/environment';

export const load = async () => {
	if (browser) {
		posthog.init('phc_sGqtRHbSH8yHBsY9SsexmXymJ9zoKu7QSWuL4uKenrE', {
			api_host: 'https://eu.i.posthog.com',
			defaults: '2025-05-24',
			person_profiles: 'always' // or 'always' to create profiles for anonymous users as well
		});
	}

	return;
};
