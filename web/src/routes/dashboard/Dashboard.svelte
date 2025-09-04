<script lang="ts">
	import Chart from './Chart.svelte';
	import PortfolioSelector from './PortfolioSelector.svelte';
	import YTDPerformanceChart from './YTDPerformanceChart.svelte';
	import VarModelSelector from './VarModelSelector.svelte';
	import VarComparisonChart from './VarComparisonChart.svelte';
	import PortfolioSelector2 from './PortfolioSelector2.svelte';
	import ExAnteVolChart from './ExAnteVolChart.svelte';

	interface DayMeasure {
		portfolioId: string;
		date: string;
		measure: string | null;
		value: string | null;
	}

	type VarMeasure = {
		id: string;
		name: string;
		spec: unknown;
	};

	interface Props {
		ptfs: Array<{ id: string; name: string; assetClass: string }>;
		ytdPerformance: Array<{
			portfolioId: string;
			startValue: number;
			endValue: number;
			performance: number;
		}>;
		dayMeasures: DayMeasure[];
		varMeasures: VarMeasure[];
	}

	let { ptfs, ytdPerformance, dayMeasures, varMeasures }: Props = $props();

	let selectedPortfolioIds = $state<string[]>([]);
	let selectedVarModel = $state<VarMeasure>(varMeasures[0]);

	$effect(() => {
		if (selectedPortfolioIds.length === 0 && ptfs.length > 0) {
			const assetClassCounts = ptfs.reduce(
				(acc, p) => {
					acc[p.assetClass] = (acc[p.assetClass] || 0) + 1;
					return acc;
				},
				{} as Record<string, number>
			);

			const largestAssetClass = Object.entries(assetClassCounts).sort(
				([, a], [, b]) => b - a
			)[0]?.[0];

			if (largestAssetClass) {
				const portfoliosInLargestClass = ptfs
					.filter((p) => p.assetClass === largestAssetClass)
					.map((p) => p.id);
				selectedPortfolioIds = portfoliosInLargestClass;
			}
		}
	});

	function handleSelectionChange(ids: string[]) {
		selectedPortfolioIds = ids;
	}

	function handleVarModelChange(model: VarMeasure) {
		selectedVarModel = model;
	}

	console.log(varMeasures);
</script>

<!-- The dashboard -->

<div class="flex h-full flex-col lg:flex-row">
	<!-- Fixed left sidebar -->
	<div
		class="w-full overflow-x-auto border-r border-base-200 p-6 lg:w-80 lg:overflow-x-visible lg:overflow-y-auto"
	>
		<div class="space-y-8">
			<PortfolioSelector2 portfolios={ptfs} onSelectionChange={handleSelectionChange} />
			<VarModelSelector
				selectedModel={selectedVarModel}
				onModelChange={handleVarModelChange}
				{varMeasures}
			/>
		</div>
	</div>

	<!-- Main content area -->
	<div class="flex-1 overflow-y-auto p-6">
		<div class="space-y-6">
			<YTDPerformanceChart {ytdPerformance} portfolios={ptfs} {selectedPortfolioIds} />
			<VarComparisonChart
				{dayMeasures}
				portfolios={ptfs}
				{selectedPortfolioIds}
				{selectedVarModel}
			/>
			<ExAnteVolChart {dayMeasures} portfolios={ptfs} {selectedPortfolioIds} />
		</div>
	</div>
</div>
