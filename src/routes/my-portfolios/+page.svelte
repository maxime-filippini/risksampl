<script lang="ts">
	import type { PageData } from './$types';

	export let data: PageData;
</script>

<main class="flex flex-col gap-8">
	<h1 class="text-4xl font-semibold">My portfolios</h1>

	<p>
		Voluptate excepteur tempor elit excepteur aliqua consequat eu et deserunt eiusmod incididunt
		quis officia minim. Eiusmod irure exercitation occaecat fugiat sunt elit deserunt laboris culpa.
		Nulla voluptate non dolore minim dolor proident excepteur adipisicing eu adipisicing nostrud.
		Minim adipisicing cupidatat velit commodo.
	</p>

	<h2 class="text-2xl font-semibold">Global portfolios</h2>

	{#if data.nGlobalPortfolios == 0}
		<p>No global portfolio available as of yet!</p>
	{/if}

	<h2 class="text-2xl font-semibold">Custom portfolios</h2>

	{#if data.nCustomPortfolios == 0}
		<p>You have no custom portfolios!</p>
	{/if}
</main>
