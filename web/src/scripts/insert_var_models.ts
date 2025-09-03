import { drizzle } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';
import { VarModelTable } from '$lib/server/db/schema';
import type { VarSpec } from '$lib/var_types';

const client = postgres(process.env.DATABASE_URL!);
const db = drizzle(client);

const main = async (model: { id: string; name: string; spec: VarSpec }) => {
	try {
		await db.insert(VarModelTable).values(model);
		console.log('Successfully inserted VaR model');
	} catch (error) {
		console.error('Error inserting VaR model:', error);
	} finally {
		await client.end();
	}
};

main({
	id: 'historical_conf=99_lookback=500',
	name: 'historical_conf=99_lookback=500',
	spec: {
		confidenceLevel: 0.99,
		filterSpec: null,
		quantileSpec: {
			type: 'sample',
			interpolation: null,
			lookback: 500
		}
	}
});
