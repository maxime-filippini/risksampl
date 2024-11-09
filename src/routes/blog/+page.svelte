<script lang="ts">
	let { data } = $props();
</script>

<h1>This is a blog</h1>

{#each data.summaries as { slug, title }}
	<li><a href="/blog/{slug}">{title}</a></li>
{/each}
