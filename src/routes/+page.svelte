<script lang="ts">
	import { page } from '$app/stores';
	import { SignIn, SignOut } from '@auth/sveltekit/components';
	const { data } = $props();
</script>

<h1 class="mb-8 text-5xl font-bold">Hello from SvelteKit</h1>

<div>
	{#if data.session}
		<SignOut />
	{:else}
		<SignIn provider="google" signInPage="signin" />
	{/if}
</div>
