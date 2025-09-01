import { sentrySvelteKit } from '@sentry/sveltekit';
import devtoolsJson from 'vite-plugin-devtools-json';
import tailwindcss from '@tailwindcss/vite';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sentrySvelteKit({
			sourceMapsUploadOptions: {
				org: 'maxime-filippini',
				project: 'javascript-sveltekit'
			}
		}),
		tailwindcss(),
		sveltekit(),
		devtoolsJson()
	],
	server: {
		allowedHosts: ['mmbp.follow-scylla.ts.net']
	}
});
