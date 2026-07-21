<script lang="ts">
	import Chart from './Chart.svelte';
	import type { EChartsCoreOption } from 'echarts/core';
	import type { ChartTooltipParameter } from './chart_tooltip';

	interface DayMeasure {
		portfolioId: string;
		date: string;
		measure: string | null;
		value: string | null;
	}

	interface Portfolio {
		id: string;
		name: string;
		assetClass: string;
	}

	interface Props {
		dayMeasures: DayMeasure[];
		portfolios: Portfolio[];
		selectedPortfolioIds: string[];
	}

	let { dayMeasures, portfolios, selectedPortfolioIds }: Props = $props();

	let volMeasures = $derived(dayMeasures.filter((item) => item.measure == 'ex_ante_volatility'));

	const chartOption = $derived.by(() => {
		const portfolioMap = new Map(portfolios.map((p) => [p.id, p.name]));

		const filteredMeasures = volMeasures.filter((measure) =>
			selectedPortfolioIds.includes(measure.portfolioId)
		);

		const data = filteredMeasures
			.map((measure) => ({
				name: portfolioMap.get(measure.portfolioId) || measure.portfolioId,
				value: Math.abs(parseFloat(measure.value || '0')) * 100, // Convert to percentage and take absolute value
				portfolioId: measure.portfolioId
			}))
			.sort((a, b) => b.value - a.value); // Sort from highest to lowest VaR

		const option: EChartsCoreOption = {
			textStyle: {
				fontFamily: 'IBM Plex Mono'
			},
			title: {
				text: `Annualized ex-ante volatility`,
				left: 'center',
				textStyle: {
					fontSize: 16,
					fontWeight: 'bold'
				}
			},
			tooltip: {
				trigger: 'axis',
				axisPointer: {
					type: 'shadow'
				},
				formatter: (params: ChartTooltipParameter | ChartTooltipParameter[]) => {
					const data = Array.isArray(params) ? params[0] : params;
					if (!data) return '';

					return `${data.name}<br/>Ex-ante volatility: ${Number(data.value).toFixed(2)}%`;
				}
			},
			grid: {
				left: '3%',
				right: '4%',
				bottom: '10%',
				top: '15%',
				containLabel: true
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
				name: 'Volatility (%)',
				nameLocation: 'middle',
				nameGap: 40,
				axisLabel: {
					formatter: '{value}%'
				}
			},
			series: [
				{
					type: 'bar',
					data: data.map((d) => ({
						value: parseFloat(d.value.toFixed(2)),
						itemStyle: {
							color: '#ef9f76'
						}
					})),
					emphasis: {
						focus: 'series'
					},
					label: {
						show: true,
						position: 'top',
						rotate: data.length < 15 ? 0 : 90,
						formatter: (params: ChartTooltipParameter) => `${Number(params.value).toFixed(2)}%`,
						offset: data.length < 15 ? [0, 0] : [25, 5]
					}
				}
			]
		};

		return option;
	});
</script>

<div class="w-full overflow-x-auto">
	<div class="flex min-w-[600px] justify-center">
		<Chart option={chartOption} height={600} />
	</div>
</div>
