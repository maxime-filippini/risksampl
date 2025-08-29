<script lang="ts">
	import type { PageProps } from './$types';
	import Table from './Table.svelte';

	let { data }: PageProps = $props();
</script>

<div class="flex flex-col gap-4 p-4">
	<h1 class="mb-8 text-2xl font-semibold">Coverage</h1>

	<h2 class="text-xl font-semibold">All instruments</h2>
	<Table
		pageSize={5}
		data={data.insts}
		columns={{
			name: 'Name',
			ticker: 'Ticker',
			currency: 'Currency'
		}}
	/>

	<div class="my-12 border-b border-base-300"></div>

	<h2 class="text-xl font-semibold">All portfolios</h2>
	<Table
		pageSize={5}
		data={data.ptfs}
		columns={{
			name: 'Name',
			currency: 'Currency'
		}}
	/>
</div>
