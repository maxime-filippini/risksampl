<!-- ELine.svelte (Svelte 5 / runes) -->
<script lang="ts">
	import * as echarts from 'echarts/core';
	import type { EChartsCoreOption, ECharts } from 'echarts/core';
	import { BarChart, LineChart } from 'echarts/charts';
	import {
		GridComponent,
		TooltipComponent,
		LegendComponent,
		TitleComponent
	} from 'echarts/components';
	import { CanvasRenderer, SVGRenderer } from 'echarts/renderers';

	// tree-shaken setup: only what we use
	echarts.use([
		LineChart,
		BarChart,
		GridComponent,
		TooltipComponent,
		LegendComponent,
		TitleComponent,
		CanvasRenderer,
		SVGRenderer
	]);

	// default option (used if you don't pass your own)
	const defaultOption: EChartsCoreOption = {
		title: { text: 'Sample Trend' },
		tooltip: { trigger: 'axis' },
		grid: { left: 40, right: 16, top: 48, bottom: 32, containLabel: true },
		xAxis: {
			type: 'category',
			boundaryGap: false,
			data: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
		},
		yAxis: { type: 'value' },
		series: [
			{
				name: 'Value',
				type: 'line',
				smooth: true,
				symbol: 'circle',
				symbolSize: 6,
				data: [120, 132, 101, 134, 90, 230, 210]
			}
		],
		legend: { bottom: 0 }
	};

	// props (all optional)
	interface Props {
		option?: EChartsCoreOption;
		theme?: string | object;
		renderer?: 'canvas' | 'svg';
		autoresize?: boolean;
		height?: number;
	}

	let {
		option = defaultOption, // your ECharts option (falls back to defaults)
		theme = undefined, // 'dark' or a custom theme object name you registered
		renderer = 'canvas', // 'canvas' | 'svg'
		autoresize = true, // keep chart sized to its container
		height = 500 // px
	}: Props = $props();
</script>

<div
	style={`width:100%;height:${height}px`}
	{@attach (el: HTMLDivElement) => {
		// if theme/renderer change, attachment re-runs with cleanup
		void theme;
		void renderer;

		const chart: ECharts = echarts.init(el, theme, { renderer });

		const ro = autoresize ? new ResizeObserver(() => chart.resize()) : null;
		ro?.observe(el);

		// fast reactive updates: re-apply option when it changes
		$effect(() => {
			chart.setOption(option, { lazyUpdate: true });
		});

		return () => {
			ro?.disconnect();
			chart.dispose();
		};
	}}
></div>
