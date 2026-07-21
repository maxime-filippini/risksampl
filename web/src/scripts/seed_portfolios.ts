import { drizzle } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';
import { instruments, portfolios, investments } from '$lib/server/db/schema';

// Get database connection
const client = postgres(process.env.DATABASE_URL!);
const db = drizzle(client);

async function seedPortfoliosAndInvestments() {
	try {
		console.log('Fetching instruments...');

		// Get all instruments
		const allInstruments = await db.select().from(instruments);
		console.log(`Found ${allInstruments.length} instruments`);

		for (const instrument of allInstruments) {
			console.log(`Processing ${instrument.name} (${instrument.ticker})`);

			// Create portfolio with same name and currency as instrument
			const portfolioId = crypto.randomUUID();
			await db.insert(portfolios).values({
				id: portfolioId,
				name: instrument.name,
				currency: instrument.currency,
				assetClass: instrument.assetClass
			});

			// Create investment of 1000 shares on 01/01/2000
			await db.insert(investments).values({
				id: crypto.randomUUID(),
				date: '2000-01-01',
				portfolioId: portfolioId,
				instrumentId: instrument.id,
				quantity: '1000'
			});

			console.log(`✓ Created portfolio and investment for ${instrument.name}`);
		}

		console.log('✅ All portfolios and investments created successfully!');
	} catch (error) {
		console.error('❌ Error seeding data:', error);
	} finally {
		await client.end();
	}
}

seedPortfoliosAndInvestments();
