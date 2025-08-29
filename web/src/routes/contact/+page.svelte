<script lang="ts">
	import type { PageProps } from './$types';

	let { form }: PageProps = $props();

	let fieldErrors = form?.errors?.fieldErrors;
	let formErrors = form?.errors?.formErrors;
</script>

<div class="mx-auto w-3xl">
	{#if form?.success}
		<p>Request sent successfully!</p>
	{:else}
		<p>
			A new feature you would like? Any other request? Fill the form below and we will get back to
			you!
		</p>

		<div class="my-8"></div>
		<form method="POST" action="?/contact">
			<h1 class="mt-12 mb-4 text-xl font-semibold">Contact us</h1>
			<fieldset class="fieldset w-full">
				<legend class="fieldset-legend">Your email address</legend>
				<input name="email" class="input w-full" type="email" value={form?.data?.email ?? ''} />
				{#if fieldErrors?.email}
					{#each fieldErrors.email as err}
						<div class="mt-1 text-sm text-error">{err}</div>
					{/each}
				{/if}
			</fieldset>
			<fieldset class="fieldset w-full">
				<legend class="fieldset-legend">Request type</legend>
				<select
					name="requestType"
					class="select w-full"
					value={form?.data?.requestType ?? 'keep-me-posted'}
				>
					<option value="keep-me-posted">Keep me posted of future updates</option>
					<option value="new-feature">New feature</option>
					<option value="doesnt-work">Something doesn't work</option>
					<option value="other-inquiry">Other inquiry</option>
				</select>
				{#if fieldErrors?.requestType}
					{#each fieldErrors.requestType as err}
						<div class="mt-1 text-sm text-error">An error occurred on this field.</div>
					{/each}
				{/if}
			</fieldset>
			<fieldset class="fieldset">
				<legend class="fieldset-legend">Your request (Optional)</legend>
				<textarea
					class="textarea w-full"
					name="request"
					placeholder="Describe your request in more details"
					value={form?.data?.request ?? ''}
				></textarea>
				{#if fieldErrors?.request}
					{#each fieldErrors.request as err}
						<div class="mt-1 text-sm text-error">{err}</div>
					{/each}
				{/if}
			</fieldset>
			<button class="btn mt-8 w-full btn-primary">Submit</button>
			{#if formErrors}
				{#each formErrors as err}
					<div class="mt-1 text-sm text-error">{err}</div>
				{/each}
			{/if}
		</form>
	{/if}
</div>
