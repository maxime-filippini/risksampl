<script lang="ts">
	interface Props {
		selectedModel: string;
		varMeasures: { id: string; name: string; spec: unknown }[];
		onModelChange: (model: string) => void;
	}

	let { selectedModel, onModelChange, varMeasures }: Props = $props();
</script>

<div class="space-y-4">
	<div>
		<h3 class="text-lg font-medium">VaR model</h3>
	</div>

	<div class="flex flex-wrap gap-3 lg:flex-col lg:flex-nowrap">
		{#each varMeasures as model (model.id)}
			<div class="max-sm:w-full sm:tooltip sm:tooltip-top">
				<label class="flex cursor-pointer items-center space-x-2 rounded border bg-base-200/30 p-3">
					<input
						type="radio"
						name="modelselection"
						checked={selectedModel === model.id}
						onchange={() => onModelChange(model.id)}
						class="radio radio-sm"
					/>
					<div>
						<span class="text-sm font-medium">{model.name} </span>
					</div>
				</label>
			</div>
		{/each}
	</div>
</div>
