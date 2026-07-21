<script
	lang="ts"
	generics="Row extends Record<string, unknown>, Cols extends Partial<Record<keyof Row, string>>"
>
	import type { Snippet } from 'svelte';

	interface Props {
		pageSize: number;
		columns: Cols;
		data: Row[];
		actions?: Snippet<[Row, number]>;
	}
	let { pageSize, data, columns, actions }: Props = $props();

	let currentPage = $state(0);

	let page = $derived.by(() => {
		const start = currentPage * pageSize;
		return data.slice(start, start + pageSize);
	});

	let totalPages = $derived(Math.ceil(data.length / pageSize));

	const nextPage = () => {
		if (currentPage < totalPages - 1) {
			currentPage++;
		}
	};

	const prevPage = () => {
		if (currentPage > 0) {
			currentPage--;
		}
	};
</script>

{#if totalPages === 0}
	<p>No entries.</p>
{:else}
	<div class="flex items-center justify-center gap-2 px-8">
		<div class="sm:mr-auto"></div>
		<button class="btn join-item" disabled={currentPage === 0} onclick={prevPage}>
			Previous
		</button>
		<p class="mx-4 px-4">{currentPage + 1}/{totalPages}</p>
		<button class="btn join-item" disabled={currentPage === totalPages - 1} onclick={nextPage}>
			Next
		</button>
	</div>
	<div class="overflow-x-auto">
		<table class="table w-full table-auto">
			<thead>
				<tr>
					<th>#</th>
					{#each Object.values(columns) as col (col)}
						<th>{col}</th>
					{/each}
					{#if actions}
						<th>Actions</th>
					{/if}
				</tr>
			</thead>
			<tbody>
				{#each page as inst, ix (inst)}
					<tr class="duration-100 hover:bg-base-300">
						<td>{currentPage * pageSize + ix + 1}</td>
						{#each Object.keys(columns) as col (col)}
							<td>{inst[col as keyof typeof inst]}</td>
						{/each}
						{#if actions}
							<td class="">
								{@render actions(inst, currentPage * pageSize + ix)}
							</td>
						{/if}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}
