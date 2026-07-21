<script lang="ts">
	import Table from '../../coverage/Table.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();
</script>

<div class="flex flex-col gap-8">
	<h1 class="text-2xl font-semibold">{data.ptf.name}</h1>

	<div class="flex flex-col gap-4">
		<h2 class="text-xl">Investment history</h2>
		<Table
			pageSize={10}
			data={data.investments}
			columns={{ date: 'Date', instrument: 'Instrument', quantity: 'Quantity' }}
		/>
	</div>
</div>
