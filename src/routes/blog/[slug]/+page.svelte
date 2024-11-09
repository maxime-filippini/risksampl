<script lang="ts">
	let { data } = $props();
</script>

<h1 class="mb-4 text-2xl font-bold">{data.post.title}</h1>
<div>{@html data.post.content}</div>
<a href="/blog">Back to index</a>
