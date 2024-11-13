<script lang="ts">
	import type { PageData } from './$types';

	export let data: PageData;
</script>

<main class="flex flex-col gap-4">
	<h1 class="text-4xl font-semibold">Portfolios</h1>
	<p>TBD</p>

	{#if data.nPtf == 0}
		<p>You have no portfolio!</p>
	{/if}
</main>
