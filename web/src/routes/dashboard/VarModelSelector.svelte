<script lang="ts">
	interface Props {
		selectedModel: string;
		onModelChange: (model: string) => void;
	}

	let { selectedModel, onModelChange }: Props = $props();

	const varModels = [
		{
			id: 'hist_var',
			name: 'Historical Simulations',
			tooltip: 'Confidence level of 99%, 500 days of lookback window'
		},
		{
			id: 'ewma_var',
			name: 'EWMA',
			tooltip: 'Confidence level of 99%, 500 days of lookback window, decay factor set to 0.94%'
		},
		{
			id: 'param_var',
			name: 'Gaussian',
			tooltip:
				'Confidence level of 99%, 250 days of lookback window, sample volatility, Gaussian distribution'
		}
	];
</script>

<div class="space-y-4">
	<div>
		<h3 class="text-lg font-medium">VaR model</h3>
	</div>

	<div class="flex flex-wrap gap-3 lg:flex-col lg:flex-nowrap">
		{#each varModels as model (model.id)}
			<div class="tooltip tooltip-top" data-tip={model.tooltip}>
				<label
					class="flex cursor-pointer items-center space-x-2 rounded border bg-base-200/30 p-3 lg:w-full"
				>
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
