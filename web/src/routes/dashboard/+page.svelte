<script lang="ts">
	import Dashboard from './Dashboard.svelte';

	const { data } = $props();
</script>

<div class="flex flex-col lg:fixed lg:inset-0 lg:top-16 lg:overflow-hidden">
	<div class="flex-shrink-0 border-b border-gray-200 px-6 py-4">
		<h1 class="flex flex-col sm:block">
			<span class="text-2xl font-semibold">Dashboard</span>
			<span class="font-base text-base">(as of {data.lastBusinessDayStr})</span>
		</h1>
	</div>

	<div class="mx-0 my-8 block bg-warning/50 p-8 sm:hidden">
		<p class="text-center">
			For a better experience, either turn your phone sideways, or access the site on a computer.
		</p>
	</div>

	<div class="flex-1 overflow-hidden">
		<Dashboard
			ptfs={data.ptfs}
			ytdPerformance={data.ytdPerformance}
			dayMeasures={data.dayMeasures}
			varMeasures={data.varMeasures}
		/>
	</div>
</div>
