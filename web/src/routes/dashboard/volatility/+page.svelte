<script lang="ts">
	import { getContext } from 'svelte';
	import ExAnteVolChart from '../ExAnteVolChart.svelte';

	let { data } = $props();
	const selectedPortfolioIds: () => string[] = getContext('selectedPortfolioIds');
</script>

<ExAnteVolChart
	portfolios={data.ptfs}
	dayMeasures={data.dayMeasures}
	selectedPortfolioIds={selectedPortfolioIds()}
/>
