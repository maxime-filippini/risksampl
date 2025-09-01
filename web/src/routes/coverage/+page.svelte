<script lang="ts">
	import type { PageProps } from './$types';
	import Table from './Table.svelte';

	let { data }: PageProps = $props();
</script>

<div class="mx-auto flex max-w-5xl flex-col gap-4">
	<h1 class="text-2xl font-semibold">Coverage</h1>
	<p>Explore the instruments currently included in the dashboard.</p>
	<Table
		pageSize={10}
		data={data.insts}
		columns={{
			name: 'Name',
			ticker: 'Ticker',
			currency: 'Currency',
			min_date: 'Min. date',
			max_date: 'Max. date'
		}}
	/>
</div>
