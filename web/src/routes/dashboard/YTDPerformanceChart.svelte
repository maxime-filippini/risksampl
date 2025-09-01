<script lang="ts">
	import Chart from './Chart.svelte';
	import type { EChartsCoreOption } from 'echarts/core';

	interface YTDPerformance {
		portfolioId: string;
		startValue: number;
		endValue: number;
		performance: number;
	}

	interface Portfolio {
		id: string;
		name: string;
		assetClass: string;
	}

	interface Props {
		ytdPerformance: YTDPerformance[];
		portfolios: Portfolio[];
		selectedPortfolioIds: string[];
	}

	let { ytdPerformance, portfolios, selectedPortfolioIds }: Props = $props();

	const chartOption = $derived.by(() => {
		const portfolioMap = new Map(portfolios.map((p) => [p.id, p.name]));

		const filteredPerformance = ytdPerformance.filter((perf) =>
			selectedPortfolioIds.includes(perf.portfolioId)
		);

		const data = filteredPerformance
			.sort((a, b) => a.performance - b.performance)
			.map((perf) => ({
				name: portfolioMap.get(perf.portfolioId) || perf.portfolioId,
				value: perf.performance,
				itemStyle: {
					color: perf.performance >= 0 ? '#22c55e' : '#ef4444'
				}
			}));

		let isLongSeries = data.length > 5;

		let tooltip = {
			trigger: 'axis',
			axisPointer: {
				type: 'shadow'
			},
			formatter: (params: any) => {
				const data = params[0];
				return `${data.name}<br/>Performance: ${data.value.toFixed(2)}%`;
			}
		};

		const option: EChartsCoreOption = {
			title: {
				text: 'YTD Portfolio Performance (%)',
				left: 'center',
				textStyle: {
					fontSize: 16,
					fontWeight: 'bold'
				}
			},
			tooltip: tooltip,
			grid: {
				left: '3%',
				right: '4%',
				bottom: '10%',
				top: '15%',
				containLabel: false
			},
			xAxis: {
				type: 'category',
				data: data.map((d) => d.name),
				axisLabel: {
					rotate: data.length > 5 ? 45 : 0,
					interval: 0
				}
			},
			yAxis: {
				type: 'value',
				name: 'Performance (%)',
				nameLocation: 'middle',
				nameGap: 40,
				axisLabel: {
					formatter: (value: number) => `${value.toFixed(2)}%`
				}
			},
			series: [
				{
					type: 'bar',
					data: data,
					emphasis: {
						focus: 'series'
					},
					label: {
						show: true,
						position: 'top',
						rotate: data.length < 15 ? 0 : 90,
						formatter: (params: any) => `${params.value.toFixed(2)}%`,
						offset: data.length < 15 ? [0, 0] : [25, 5]
					}
				}
			]
		};

		return option;
	});
</script>

<div class="w-full overflow-x-auto">
	<div class="min-w-[600px] flex justify-center">
		<Chart option={chartOption} height={600} />
	</div>
</div>
