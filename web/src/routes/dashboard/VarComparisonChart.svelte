<script lang="ts">
	import Chart from './Chart.svelte';
	import type { EChartsCoreOption } from 'echarts/core';

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
		selectedVarModel: string;
	}

	let { dayMeasures, portfolios, selectedPortfolioIds, selectedVarModel }: Props = $props();

	const chartOption = $derived.by(() => {
		const portfolioMap = new Map(portfolios.map((p) => [p.id, p.name]));

		const filteredMeasures = dayMeasures.filter(
			(measure) =>
				selectedPortfolioIds.includes(measure.portfolioId) &&
				measure.measure === selectedVarModel &&
				measure.value !== null &&
				measure.measure !== null
		);

		const data = filteredMeasures
			.map((measure) => ({
				name: portfolioMap.get(measure.portfolioId) || measure.portfolioId,
				value: Math.abs(parseFloat(measure.value || '0')) * 100, // Convert to percentage and take absolute value
				portfolioId: measure.portfolioId
			}))
			.sort((a, b) => b.value - a.value); // Sort from highest to lowest VaR

		const option: EChartsCoreOption = {
			title: {
				text: `VaR Comparison (${getModelName(selectedVarModel)})`,
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
				formatter: (params: any) => {
					const data = params[0];
					return `${data.name}<br/>VaR: ${data.value.toFixed(2)}%`;
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
				name: 'VaR (%)',
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
							color: '#ef4444' // Red color for VaR (risk)
						}
					})),
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

	function getModelName(model: string): string {
		const modelNames: Record<string, string> = {
			hist_var: 'Historical Simulations',
			ewma_var: 'EWMA',
			param_var: 'Gaussian'
		};
		return modelNames[model] || model;
	}
</script>

<div class="w-full overflow-x-auto">
	<div class="min-w-[600px] flex justify-center">
		<Chart option={chartOption} height={600} />
	</div>
</div>
