<script lang="ts">
	import { getContext } from 'svelte';
	import YtdPerformanceChart from '../YTDPerformanceChart.svelte';

	let { data } = $props();
	const selectedPortfolioIds: () => string[] = getContext('selectedPortfolioIds');
</script>

<YtdPerformanceChart
	ytdPerformance={data.ytdPerformance}
	portfolios={data.ptfs}
	selectedPortfolioIds={selectedPortfolioIds()}
/>
