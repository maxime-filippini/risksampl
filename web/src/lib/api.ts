import createClient from 'openapi-fetch';
import type { paths } from './types/api';

// For server-to-server requests, we need to use the URL for the service.
const getBaseUrl = () => {
	return process.env.API_URL;
};

export const createApiClient = (fetch?: typeof globalThis.fetch) => {
	const baseUrl = getBaseUrl();

	return createClient<paths>({
		baseUrl: baseUrl,
		fetch
	});
};
