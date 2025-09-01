<script lang="ts">
	interface Portfolio {
		id: string;
		name: string;
		assetClass: string;
	}

	interface Props {
		portfolios: Portfolio[];
		selectedPortfolioIds: string[];
		onSelectionChange: (ids: string[]) => void;
	}

	let { portfolios, selectedPortfolioIds, onSelectionChange }: Props = $props();

	const assetClasses = $derived.by(() => {
		const assetClassCounts = portfolios.reduce(
			(acc, p) => {
				acc[p.assetClass] = (acc[p.assetClass] || 0) + 1;
				return acc;
			},
			{} as Record<string, number>
		);

		return Object.entries(assetClassCounts)
			.sort(([, a], [, b]) => b - a)
			.map(([assetClass]) => assetClass);
	});

	function selectAssetClass(assetClass: string) {
		const portfoliosInClass = portfolios.filter((p) => p.assetClass === assetClass);
		const portfolioIdsInClass = portfoliosInClass.map((p) => p.id);

		onSelectionChange(portfolioIdsInClass);
	}

	function selectAll() {
		onSelectionChange(portfolios.map((p) => p.id));
	}

	function isAssetClassSelected(assetClass: string) {
		const portfoliosInClass = portfolios.filter((p) => p.assetClass === assetClass);
		const portfolioIdsInClass = portfoliosInClass.map((p) => p.id);

		return (
			portfolioIdsInClass.length > 0 &&
			portfolioIdsInClass.every((id) => selectedPortfolioIds.includes(id)) &&
			selectedPortfolioIds.every((id) => portfolioIdsInClass.includes(id))
		);
	}

	function isAllSelected() {
		return (
			portfolios.length > 0 &&
			portfolios.every((p) => selectedPortfolioIds.includes(p.id)) &&
			selectedPortfolioIds.length === portfolios.length
		);
	}
</script>

<div class="space-y-4">
	<div class="flex items-center justify-between">
		<h3 class="text-lg font-medium">Asset class</h3>
	</div>

	<div class="flex flex-col gap-2">
		<label class="flex cursor-pointer items-center space-x-2 rounded border p-3">
			<input
				type="radio"
				name="assetClassSelection"
				checked={isAllSelected()}
				onchange={() => selectAll()}
				class="h-4 w-4 border-gray-300 text-blue-600 focus:ring-blue-500"
			/>
			<div>
				<span class="text-sm font-medium"
					>All Asset Classes

					<span class="text-xs text-gray-500">
						({portfolios.length})
					</span>
				</span>
			</div>
		</label>

		{#each assetClasses as assetClass (assetClass)}
			{@const portfoliosInClass = portfolios.filter((p) => p.assetClass === assetClass)}

			<label class="flex cursor-pointer items-center space-x-2 rounded border p-3">
				<input
					type="radio"
					name="assetClassSelection"
					checked={isAssetClassSelected(assetClass)}
					onchange={() => selectAssetClass(assetClass)}
					class="h-4 w-4 border-gray-300 text-blue-600 focus:ring-blue-500"
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
