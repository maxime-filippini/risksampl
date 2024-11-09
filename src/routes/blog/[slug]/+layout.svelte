<script lang="ts">
	let { data, children } = $props();
</script>

<div>
	<main>{@render children()}</main>

	<aside>
		<h2>More posts</h2>
		<ul>
			{#each data.summaries as { slug, title }}
				<li><a href="/blog/{slug}">{title}</a></li>
			{/each}
		</ul>
	</aside>
</div>
