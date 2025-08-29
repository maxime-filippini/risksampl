import { env } from '$env/dynamic/private';

export const config = {
	apiUrl: env.API_URL || 'http://localhost:8000'
};
