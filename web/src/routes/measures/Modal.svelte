<script lang="ts">
	import type { Snippet } from 'svelte';

	type Props = {
		modalOpened: string | null;
		id: string;
		measure: {
			id: string;
			name: string;
			type: 'other' | 'value_at_risk';
			spec: unknown;
		};
		children?: Snippet;
	};

	let { modalOpened = $bindable(), id, measure, children }: Props = $props();

	let dialog = $state<HTMLDialogElement>();

	$effect(() => {
		if (modalOpened === id && dialog) dialog.showModal();
	});
</script>

<dialog
	{id}
	bind:this={dialog}
	class="modal"
	onclose={() => (modalOpened = null)}
	onclick={(e) => {
		if (e.target === dialog) dialog.close();
	}}
>
	<div class="modal-box">
		{@render children?.()}
	</div>
	<form method="dialog" class="modal-backdrop">
		<button>close</button>
	</form>
</dialog>
