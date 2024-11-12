<script lang="ts">
	let { data } = $props();
</script>

<h1>Models</h1>

<div class="flex flex-col">
	{#each data.models as model}
		<div class="flex gap-8">
			<p>{model.id}</p>
			<p>{model.name}</p>
		</div>
	{/each}
</div>
