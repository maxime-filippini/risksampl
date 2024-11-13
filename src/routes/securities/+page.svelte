<script lang="ts">
	import DataTable from './data-table.svelte';
	import { columns } from './columns.js';

	let { data } = $props();
</script>

<main class="flex flex-col gap-8">
	<h1 class="text-4xl font-semibold">Securities</h1>
	<p>The application currently supports the {data.nSecurities} securities listed below.</p>
	<DataTable data={data.securities} {columns} />
</main>
