<script lang="ts">
	import '../app.css';
	import Navbar from './Navbar.svelte';
	import { navigating } from '$app/state';

	let { children } = $props();
</script>

<svelte:head>
	<title>Risksampl - Daily Dynamic Risk Dashboard</title>
	<meta
		name="description"
		content="A daily dynamic dashboard to help you contextualize your risk measures by comparing them against other portfolios. Built with ❤️ by Maxime Filippini."
	/>

	<!-- Open Graph / Facebook -->
	<meta property="og:type" content="website" />
	<meta property="og:url" content="https://risksampl.com/" />
	<meta property="og:title" content="Risksampl - Daily Dynamic Risk Dashboard" />
	<meta
		property="og:description"
		content="A daily dynamic dashboard to help you contextualize your risk measures by comparing them against other portfolios. Built with ❤️ by Maxime Filippini."
	/>
	<meta name="image" property="og:image" content="https://risksampl.com/og-image.svg" />
	<meta property="og:image:width" content="1200" />
	<meta property="og:image:height" content="630" />
	<meta property="og:site_name" content="Risksampl" />

	<!-- Twitter -->
	<meta name="twitter:card" content="summary_large_image" />
	<meta name="twitter:url" content="https://risksampl.com/" />
	<meta name="twitter:title" content="Risksampl - Daily Dynamic Risk Dashboard" />
	<meta
		name="twitter:description"
		content="A daily dynamic dashboard to help you contextualize your risk measures by comparing them against other portfolios. Built with ❤️ by Maxime Filippini."
	/>
	<meta name="twitter:image" content="https://risksampl.com/og-image.svg" />
	<meta name="twitter:creator" content="@maxfilippini" />

	<!-- Additional SEO -->
	<meta name="author" content="Maxime Filippini" />
	<meta
		name="keywords"
		content="risk management, portfolio analysis, financial dashboard, risk measures, investment analysis"
	/>
	<link rel="canonical" href="https://risksampl.com/" />

	<link
		rel="icon"
		href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📊</text></svg>"
	/>
</svelte:head>

<Navbar />

<div class="bg-base-100 px-8 py-24 font-mono">
	{#if navigating.from}
		<div class="fixed inset-0 top-16 z-50 flex items-center justify-center bg-base-100">
			<span class="loading loading-xl loading-spinner"></span>
		</div>
	{/if}
	{@render children?.()}
</div>
