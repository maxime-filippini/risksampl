<script lang="ts">
	import { varSpec } from '$lib/var_types';

	let {
		measure
	}: {
		measure: {
			id: string;
			name: string;
			type: 'value_at_risk' | 'other';
			spec: unknown;
		};
	} = $props();

	console.log(measure.spec);
	let spec = varSpec.parse(measure.spec);
</script>

<div class="flex flex-col gap-4">
	<h1 class="text-xl font-semibold">{measure.name}</h1>
	<h2 class="text-lg">Distribution</h2>
	{#if spec.quantileSpec.type === 'distribution'}
		<p class="font-sm italic">{spec.quantileSpec.distribution}</p>
	{:else}
		<p class="font-sm italic">No distribution assumption.</p>
	{/if}

	<h2 class="text-lg">Filter specification</h2>
	{#if spec.filterSpec}
		<p class="font-sm italic">{JSON.stringify(spec.filterSpec)}</p>
	{:else}
		<p class="font-sm italic">No filter applied</p>
	{/if}

	<h2 class="text-lg">Quantile specification</h2>

	{#if spec.quantileSpec.type === 'sample'}
		<p class="text-sm italic">The quantile is defined based on the sample returns</p>
	{:else if spec.quantileSpec.type === 'distribution'}
		<p class="text-sm italic">
			The quantile is defined based on the parametric definition of the following distribution:
		</p>
		<p class="text-sm italic">{spec.quantileSpec.distribution}</p>
	{/if}

	<p class="font-sm italic">{JSON.stringify(spec.quantileSpec)}</p>
</div>
