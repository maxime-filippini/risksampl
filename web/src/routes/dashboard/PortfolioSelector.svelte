<script lang="ts">
	import { untrack } from 'svelte';

	type Portfolio = {
		id: string;
		name: string;
		assetClass: string;
	};

	type Props = {
		portfolios: Portfolio[];
		onSelectionChange: (ids: string[]) => void;
	};

	let { portfolios, onSelectionChange }: Props = $props();

	// Get the list of asset classes and the number of portfolios associated
	// with them
	let assetClassCounts = $derived(
		portfolios.reduce(
			(acc, p) => {
				acc[p.assetClass] = (acc[p.assetClass] || 0) + 1;
				return acc;
			},
			{} as Record<string, number>
		)
	);

	let assetClasses = $derived(
		Object.entries(assetClassCounts)
			.sort(([, a], [, b]) => b - a)
			.map(([assetClass]) => assetClass)
	);

	let allAssetClasses = $derived(['All', ...assetClasses]);

	let selectedAssetClass = $state(untrack(() => assetClasses[0]));

	let selectedPortfolios = $derived.by(() => {
		if (selectedAssetClass === 'All') {
			return portfolios;
		} else {
			return portfolios.filter((p) => p.assetClass === selectedAssetClass);
		}
	});

	let selectedPortfolioIds = $derived(selectedPortfolios.map((p) => p.id));

	// Propagate selection on mount
	$effect(() => {
		onSelectionChange(selectedPortfolioIds);
	});

	function selectAssetClass(assetClass: string) {
		selectedAssetClass = assetClass;
	}
</script>

<div class="space-y-4">
	<div class="flex items-center justify-between">
		<h3 class="text-lg font-medium">Asset class</h3>
	</div>

	<div class="flex flex-row flex-wrap gap-2 lg:flex-col lg:flex-nowrap">
		{#each allAssetClasses as assetClass (assetClass)}
			{@const portfoliosInClass =
				assetClass === 'All' ? portfolios : portfolios.filter((p) => p.assetClass === assetClass)}

			<label
				class="flex cursor-pointer items-center space-x-2 rounded border bg-base-200/30 p-3 max-sm:w-full"
			>
				<input
					type="radio"
					name="assetClassSelection"
					checked={assetClass === selectedAssetClass}
					onchange={() => selectAssetClass(assetClass)}
					class="radio radio-sm"
				/>
				<div>
					<span class="text-sm font-medium"
						>{assetClass}

						<span class="text-xs text-gray-500">
							({portfoliosInClass.length})
						</span>
					</span>
				</div>
			</label>
		{/each}
	</div>
</div>
