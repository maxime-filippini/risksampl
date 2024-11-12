<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import AppSidebar from '$lib/components/app-sidebar.svelte';

	import '../app.css';
	let { children, data } = $props();

	let open = $state(true);
</script>

<Sidebar.Provider {open} controlledOpen onOpenChange={(value) => (open = value)}>
	<AppSidebar {open} />
	<main class="w-full">
		<div class="flex h-12 w-full items-center gap-4 bg-background px-4">
			<Sidebar.Trigger />
			<h2
				class="text-md font-semibold text-sidebar-accent-foreground duration-200 hover:text-sidebar-foreground"
			>
				Risksampl
			</h2>
		</div>
		<div class="m-4 rounded-lg bg-slate-50 p-8">
			{@render children?.()}
			<p>{data.session === null}</p>
		</div>
	</main>
</Sidebar.Provider>
