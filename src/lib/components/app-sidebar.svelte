<script lang="ts">
	import House from 'lucide-svelte/icons/house';
	import Inbox from 'lucide-svelte/icons/inbox';
	import Settings from 'lucide-svelte/icons/settings';
	import { ChartLine, SquareChartGantt } from 'lucide-svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import * as Tooltip from '$lib/components/ui/tooltip/index.js';

	// Menu items.
	const items = [
		{
			title: 'Home',
			url: '/',
			icon: House
		},
		{
			title: 'Models',
			url: '/models',
			icon: SquareChartGantt
		},
		{
			title: 'Settings',
			url: '/settings',
			icon: Settings
		}
	];

	let { open } = $props();
</script>

<Tooltip.Provider>
	<Sidebar.Root collapsible="icon">
		<Sidebar.Content>
			<Sidebar.Group>
				<Sidebar.GroupLabel>Application</Sidebar.GroupLabel>
				<Sidebar.GroupContent>
					<Sidebar.Menu>
						{#each items as item (item.title)}
							<Sidebar.MenuItem>
								<Sidebar.MenuButton>
									{#snippet child({ props })}
										{#if open}
											<a href={item.url} {...props}>
												<item.icon />
												<span>{item.title}</span>
											</a>
										{:else}
											<Tooltip.Root delayDuration={100}>
												<Tooltip.Trigger>
													<a href={item.url} {...props}>
														<item.icon />
														<span>{item.title}</span>
													</a>
												</Tooltip.Trigger>
												<Tooltip.Content side="right" sideOffset={10}>
													<p>{item.title}</p>
												</Tooltip.Content>
											</Tooltip.Root>
										{/if}
									{/snippet}
								</Sidebar.MenuButton>
							</Sidebar.MenuItem>
						{/each}
					</Sidebar.Menu>
				</Sidebar.GroupContent>
			</Sidebar.Group>
		</Sidebar.Content>
	</Sidebar.Root>
</Tooltip.Provider>
