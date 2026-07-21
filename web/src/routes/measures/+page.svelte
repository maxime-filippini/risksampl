<script lang="ts">
	import Table from '../coverage/Table.svelte';
	import type { PageProps } from './$types';
	import Modal from './Modal.svelte';
	import VarSpecs from './VarSpecs.svelte';

	let { data }: PageProps = $props();
	let modalOpened = $state<string | null>(null);
</script>

{#snippet specButton(row: (typeof data.measures)[0])}
	<button class="btn w-full btn-primary" onclick={() => (modalOpened = row.id)}>See specs</button>
	<Modal bind:modalOpened id={row.id}>
		<VarSpecs measure={row} />
	</Modal>
{/snippet}

<div class="mx-auto flex max-w-5xl flex-col gap-4">
	<h1 class="text-2xl font-semibold">VaR measures</h1>
	<Table
		pageSize={5}
		columns={{ id: 'ID', name: 'Name' }}
		data={data.measures.filter((m) => m.type === 'value_at_risk')}
		actions={specButton}
	/>

	<h1 class="text-2xl font-semibold">Other measures</h1>
	<Table
		pageSize={5}
		columns={{ id: 'ID', name: 'Name' }}
		data={data.measures.filter((m) => m.type !== 'value_at_risk')}
	/>
</div>
