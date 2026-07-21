<script lang="ts">
	import { varSpec } from '$lib/var_types';

	let {
		measure
	}: {
		measure: {
			name: string;
			spec: unknown;
		};
	} = $props();

	let spec = $derived(varSpec.parse(measure.spec));
</script>

<div class="flex flex-col gap-4">
	<h1 class="text-xl font-semibold">{measure.name}</h1>

	<h2 class="text-lg">Quantile specification</h2>

	{#if spec.quantileSpec.type === 'sample'}
		<p class="text-sm italic">The quantile is defined based on the sample returns</p>
	{:else if spec.quantileSpec.type === 'distribution'}
		<p class="text-sm italic">
			The quantile is defined based on the parametric definition of the following distribution:
		</p>
		<p class="text-sm italic">Distribution type: {spec.quantileSpec.distribution.type}</p>
		<p class="text-sm italic">Specifications for mean process:</p>
		<pre class="overflow-auto bg-base-300 px-2 py-4 text-left whitespace-pre-wrap">{JSON.stringify(
				spec.quantileSpec.distribution.meanSpec,
				null,
				2
			)}</pre>

		<p class="text-sm italic">Specifications for volatility process:</p>
		<pre class="overflow-auto bg-base-300 px-2 py-4 text-left whitespace-pre-wrap">{JSON.stringify(
				spec.quantileSpec.distribution.volSpec,
				null,
				2
			)}</pre>
	{/if}

	<h2 class="text-lg">Filter specification</h2>
	{#if spec.filterSpec}
		<pre class="overflow-auto bg-base-300 px-2 py-4 text-left whitespace-pre-wrap">
			<code>{JSON.stringify(spec.filterSpec, null, 2)}</code>
		</pre>
	{:else}
		<p class="font-sm italic">No filter applied</p>
	{/if}
</div>
