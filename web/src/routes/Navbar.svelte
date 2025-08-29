<script>
	import { navigating } from '$app/state';

	let mobileMenuOpen = $state(false);

	const toggleMobileMenu = () => {
		mobileMenuOpen = !mobileMenuOpen;
	};

	$effect(() => {
		if (!navigating.complete) {
			mobileMenuOpen = false;
		}
	});
</script>

<div
	class="bg-opacity-100 fixed z-50 navbar flex w-full flex-row justify-between border-b border-base-200 bg-base-200 px-4 font-mono shadow-sm"
>
	<a class="btn mr-auto text-xl btn-ghost" href="/">Risksampl</a>
	<div class="mr-0 hidden w-0 flex-row gap-8 sm:flex sm:ml-auto sm:w-auto sm:px-8">
		<a class="link link-hover" href="/dashboard">Dashboard</a>
		<a class="link link-hover" href="/coverage">Coverage</a>
		<a class="link link-hover" href="/contact">Contact</a>
	</div>

	<button class="btn sm:hidden" aria-label="Toggle mobile menu" onclick={toggleMobileMenu}>
		<svg
			xmlns="http://www.w3.org/2000/svg"
			fill="none"
			viewBox="0 0 24 24"
			stroke-width="1.5"
			stroke="currentColor"
			class="size-6"
		>
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5"
			/>
		</svg>
	</button>
</div>

{#if mobileMenuOpen}
	<div class="fixed top-16 right-0 left-0 z-40 border-b border-base-200 bg-base-200 sm:hidden">
		<div class="flex flex-col gap-2 p-4">
			<a class="link py-2 link-hover" href="/dashboard" onclick={toggleMobileMenu}>Dashboard</a>
			<a class="link py-2 link-hover" href="/coverage" onclick={toggleMobileMenu}>Coverage</a>
			<a class="link py-2 link-hover" href="/contact" onclick={toggleMobileMenu}>Contact</a>
		</div>
	</div>
{/if}
