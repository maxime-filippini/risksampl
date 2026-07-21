<script lang="ts">
	import Table from '../coverage/Table.svelte';

	let { data } = $props();
</script>

{#snippet actionButtons(row: (typeof data.ptfs)[0])}
	<a href="/portfolios/{row.id}" class="w-full">
		<button class="btn w-full btn-neutral">View details</button>
	</a>
{/snippet}

<div class="mx-auto flex max-w-5xl flex-col gap-4">
	<h1 class="text-2xl font-semibold">All portfolios</h1>

	<p>
		There are currently {data.ptfs.length} portfolios available in the dashboard. Explore them below.
	</p>

	<Table
		pageSize={10}
		data={data.ptfs}
		columns={{
			name: 'Name',
			currency: 'Currency'
		}}
		actions={actionButtons}
	/>
</div>
