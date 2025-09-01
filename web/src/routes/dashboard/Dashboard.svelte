<script lang="ts">
	import Chart from './Chart.svelte';
	import PortfolioSelector from './PortfolioSelector.svelte';
	import YTDPerformanceChart from './YTDPerformanceChart.svelte';
	import VarModelSelector from './VarModelSelector.svelte';
	import VarComparisonChart from './VarComparisonChart.svelte';
	import PortfolioSelector2 from './PortfolioSelector2.svelte';

	interface DayMeasure {
		portfolioId: string;
		date: string;
		measure: string | null;
		value: string | null;
	}

	interface Props {
		ptfs: Array<{ id: string; name: string; assetClass: string }>;
		ytdPerformance: Array<{
			portfolioId: string;
			startValue: number;
			endValue: number;
			performance: number;
		}>;
		dayMeasures: DayMeasure[];
	}

	let { ptfs, ytdPerformance, dayMeasures }: Props = $props();

	let selectedPortfolioIds = $state<string[]>([]);
	let selectedVarModel = $state<string>('hist_var');

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

	function handleVarModelChange(model: string) {
		selectedVarModel = model;
	}
</script>

<!-- The dashboard -->

<div class="flex flex-col h-full lg:flex-row">
	<!-- Fixed left sidebar -->
	<div class="w-full overflow-x-auto border-r border-base-200 p-6 lg:w-80 lg:overflow-y-auto lg:overflow-x-visible">
		<div class="space-y-8">
			<PortfolioSelector2 portfolios={ptfs} onSelectionChange={handleSelectionChange} />
			<VarModelSelector selectedModel={selectedVarModel} onModelChange={handleVarModelChange} />
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
		</div>
	</div>
</div>
