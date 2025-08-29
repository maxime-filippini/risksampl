<script lang="ts">
	import '../app.css';
	import favicon from '$lib/assets/favicon.svg';
	import Navbar from './Navbar.svelte';
	import { navigating } from '$app/state';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<Navbar />

<div class="bg-base-100 px-8 py-24 font-mono">
	{#if navigating.from}
		<div class="flex h-screen w-screen items-center justify-center">
			<span class="loading loading-xl loading-spinner"></span>
		</div>
	{:else}
		{@render children?.()}
	{/if}
</div>
