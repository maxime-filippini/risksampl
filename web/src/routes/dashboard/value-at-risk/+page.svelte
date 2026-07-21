<script lang="ts">
	import { getContext, untrack } from 'svelte';
	import VarComparisonChart from '../VarComparisonChart.svelte';
	import VarModelSelector from '../VarModelSelector.svelte';

	let { data } = $props();

	type VarMeasure = {
		id: string;
		name: string;
	};

	let selectedVarModel = $state<VarMeasure>(untrack(() => data.varMeasures[0]));
	const selectedPortfolioIds: () => string[] = getContext('selectedPortfolioIds');

	function onModelChange(model: VarMeasure) {
		selectedVarModel = model;
	}
</script>

<VarModelSelector selectedModel={selectedVarModel} varMeasures={data.varMeasures} {onModelChange} />

<VarComparisonChart
	portfolios={data.ptfs}
	dayMeasures={data.dayMeasures}
	selectedPortfolioIds={selectedPortfolioIds()}
	{selectedVarModel}
/>
