<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import AppSidebar from '$lib/components/app-sidebar.svelte';

	import '../app.css';
	import { SignIn, SignOut } from '@auth/sveltekit/components';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { LogOut } from 'lucide-svelte';
	let { children, data } = $props();
	let open = $state(true);

	console.log(data.session);
</script>

{#if data.session}
	<Sidebar.Provider {open} controlledOpen onOpenChange={(value) => (open = value)}>
		<AppSidebar {open} user={data.user} />
		<main class="w-full">
			<div class="flex h-12 w-full items-center gap-4 bg-background px-4">
				<Sidebar.Trigger />
				<div class="mr-auto"></div>
				<div class="rounded-full bg-black px-4 py-1 text-white">
					<p>{data.user?.email}</p>
				</div>

				<SignOut class="flex items-center justify-center">
					<LogOut slot="submitButton" />
				</SignOut>
			</div>
			<div class="m-4 rounded-lg bg-slate-50 p-8">
				{@render children?.()}
			</div>
		</main>
	</Sidebar.Provider>
{:else}
	<main class="flex h-screen w-full flex-col items-center justify-center gap-8 bg-slate-100">
		<h1 class="text-5xl font-semibold">Risksampl</h1>
		<div class="h-1/3">
			<Card.Root class="flex flex-col items-center px-16">
				<Card.Header>
					<Card.Title>Sign in to use the app</Card.Title>
				</Card.Header>
				<Card.Content>
					<SignIn signInPage="signin" provider="google">
						<div slot="submitButton">
							<Button>
								<img src="/google_logo.svg" alt="Google logo" class="mr-2" />
								<p>Sign in with Google</p>
							</Button>
						</div>
					</SignIn>
				</Card.Content>
			</Card.Root>
		</div>
	</main>
{/if}
