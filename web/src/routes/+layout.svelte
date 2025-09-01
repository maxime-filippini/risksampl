<script lang="ts">
	import '../app.css';
	import Navbar from './Navbar.svelte';
	import { navigating } from '$app/state';

	let { children } = $props();
</script>

<svelte:head>
	<link
		rel="icon"
		href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📊</text></svg>"
	/>
</svelte:head>

<Navbar />

<div class="bg-base-100 px-8 py-24 font-mono">
	{#if navigating.from}
		<div class="fixed inset-0 top-16 flex items-center justify-center bg-base-100 z-50">
			<span class="loading loading-xl loading-spinner"></span>
		</div>
	{/if}
	{@render children?.()}
</div>
