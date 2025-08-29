<script lang="ts">
	import { page } from '$app/state';
</script>

<div class="flex h-screen w-full flex-col items-center justify-center gap-8 p-8">
	<p class="text-3xl font-semibold text-red-500">Oops! An error happened!</p>
	<p class="text-xl">Sorry about that. Here's the error message:</p>
	<p class="italic">"{page.error?.message}"</p>
</div>
