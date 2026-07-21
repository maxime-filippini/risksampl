<script lang="ts">
	import { page } from '$app/state';
	import PortfolioSelector from './PortfolioSelector.svelte';
	import type { Snippet } from 'svelte';
	import { setContext } from 'svelte';

	interface Props {
		children: Snippet;
		data: {
			ptfs: Array<{ id: string; name: string; assetClass: string }>;
			lastBusinessDayStr: string;
		};
	}

	let { children, data }: Props = $props();

	let selectedPortfolioIds = $state<string[]>([]);
	type Tab = { id: string; label: string };

	const tabs: Tab[] = [
		{ id: 'performance', label: 'Performance' },
		{ id: 'volatility', label: 'Volatility' },
		{ id: 'value-at-risk', label: 'Value-at-Risk' }
	];

	function handleSelectionChange(ids: string[]) {
		selectedPortfolioIds = ids;
	}

	setContext('selectedPortfolioIds', () => selectedPortfolioIds);
</script>

<div class="flex flex-col lg:fixed lg:inset-0 lg:top-16 lg:overflow-hidden">
	<div class="flex-shrink-0 px-6 py-4">
		<h1 class="flex flex-col sm:block">
			<span class="text-2xl font-semibold">Dashboard</span>
			<span class="font-base text-base">(as of {data.lastBusinessDayStr})</span>
		</h1>
	</div>

	<!-- Tabs -->
	<div role="tablist" class="tabs gap-8 border-b border-gray-200 px-6">
		{#each tabs as tab (tab.id)}
			<a
				href={`/dashboard/${tab.id}`}
				role="tab"
				class={{ 'tab px-0': true, 'tab-active': page.route.id === `/dashboard/${tab.id}` }}
				id={tab.id}
			>
				{tab.label}
			</a>
		{/each}
	</div>

	<div class="mx-0 my-8 block bg-warning/50 p-8 sm:hidden">
		<p class="text-center">
			For a better experience, either turn your phone sideways, or access the site on a computer.
		</p>
	</div>

	<div class="flex-1 overflow-hidden">
		<div class="flex h-full flex-col lg:flex-row">
			<div
				class="w-full overflow-x-auto border-r border-base-200 p-6 lg:w-80 lg:overflow-x-visible lg:overflow-y-auto"
			>
				<div class="space-y-8">
					<PortfolioSelector portfolios={data.ptfs} onSelectionChange={handleSelectionChange} />
				</div>
			</div>
			<div class="flex-1 overflow-y-auto p-6">
				<div class="space-y-6">
					{@render children()}
				</div>
			</div>
		</div>
	</div>
</div>
