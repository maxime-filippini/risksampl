<script lang="ts" generics="Cols extends Record<string, string>">
	type RowFrom<C> = { [K in keyof C]: unknown };

	interface Props {
		pageSize: number;
		columns: Cols;
		data: RowFrom<Cols>[];
	}
	let { pageSize, data, columns }: Props = $props();

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
	<table class="table table-auto">
		<thead>
			<tr>
				<th>#</th>
				{#each Object.values(columns) as col}
					<th>{col}</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each page as inst, ix}
				<tr class="duration-100 hover:bg-base-300">
					<td>{currentPage * pageSize + ix + 1}</td>
					{#each Object.keys(columns) as col}
						<td>{inst[col as keyof typeof inst]}</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
{/if}
