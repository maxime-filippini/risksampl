<script lang="ts">
	import DataTable from './data-table.svelte';
	import { columns } from './columns.js';

	let { data } = $props();
</script>

<main class="flex flex-col gap-4">
	<h1 class="text-4xl font-semibold">Securities</h1>
	<DataTable data={data.securities} {columns} />
</main>
