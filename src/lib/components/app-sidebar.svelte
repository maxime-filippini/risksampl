<script lang="ts">
	import House from 'lucide-svelte/icons/house';
	import Inbox from 'lucide-svelte/icons/inbox';
	import Settings from 'lucide-svelte/icons/settings';
	import { ChartLine, SquareChartGantt, BriefcaseBusiness, Receipt } from 'lucide-svelte';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import * as Tooltip from '$lib/components/ui/tooltip/index.js';

	type Item = { title: string; url: string; icon: any };
	type Category = { name: string | null; items: Item[] };

	// Menu items.
	const head: Item[] = [];

	const categories: Category[] = [
		{
			name: 'Basics',
			items: [
				{
					title: 'Home',
					url: '/',
					icon: House
				}
			]
		},
		{
			name: 'My Items',
			items: [
				{
					title: 'My portfolios',
					url: '/my-portfolios',
					icon: BriefcaseBusiness
				},
				{
					title: 'My models',
					url: '/my-models',
					icon: SquareChartGantt
				}
			]
		},
		{
			name: 'Browse',
			items: [
				{
					title: 'Securities',
					url: '/securities',
					icon: Receipt
				}
			] // Empty category for demonstration
		}
	];

	const tail: Item[] = [
		{
			title: 'Settings',
			url: '/settings',
			icon: Settings
		}
	];

	const admin: Category = {
		name: 'Admin',
		items: [
			{
				title: 'Test',
				url: '/admin',
				icon: Receipt
			}
		]
	};

	let { open, user } = $props();
</script>

{#snippet SidebarMenuItem(item: Item)}
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
{/snippet}

{#snippet SidebarCategory(category: Category)}
	{#if category.items.length > 0}
		<Sidebar.Group>
			{#if category !== null}
				<Sidebar.GroupLabel>{category.name}</Sidebar.GroupLabel>
			{/if}
			<Sidebar.Menu>
				{#each category.items as item (item.title)}
					{@render SidebarMenuItem(item)}
				{/each}
			</Sidebar.Menu>
		</Sidebar.Group>
	{/if}
{/snippet}

<Tooltip.Provider>
	<Sidebar.Root collapsible="icon">
		<Sidebar.Content>
			{#each categories as category}
				{@render SidebarCategory(category)}
			{/each}
			{#if user.role == 'admin'}
				{@render SidebarCategory(admin)}
			{/if}
		</Sidebar.Content>
	</Sidebar.Root>
</Tooltip.Provider>
