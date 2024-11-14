import type { AdapterAccountType } from '@auth/core/adapters';
import { relations } from 'drizzle-orm';
import {
	pgTable,
	text,
	real,
	primaryKey,
	timestamp,
	uuid,
	jsonb,
	varchar,
	numeric,
	integer,
	boolean
} from 'drizzle-orm/pg-core';

export const role = pgTable('role', {
	name: text('name').notNull().primaryKey()
});

export const users = pgTable('user', {
	id: text('id')
		.primaryKey()
		.$defaultFn(() => crypto.randomUUID()),
	name: text('name'),
	email: text('email').unique(),
	emailVerified: timestamp('emailVerified', { mode: 'date' }),
	image: text('image'),
	role: text('role').default('user').notNull()
});

export const security = pgTable('security', {
	id: uuid('id').defaultRandom().primaryKey(),
	name: text('name').notNull(),
	symbol: text('symbol').notNull(),
	currency: text('currency').notNull(),
	typeId: uuid('typeId').references(() => securityType.id)
});

export const securityType = pgTable('securityType', {
	id: uuid('id').defaultRandom().primaryKey(),
	type: text('type').notNull()
});

export const portfolio = pgTable('portfolio', {
	id: uuid('id').defaultRandom().primaryKey(),
	name: text('name'),
	userId: text('userId')
		.notNull()
		.references(() => users.id, { onDelete: 'no action' })
});

export const securityTypeRelations = relations(securityType, ({ many }) => ({
	securities: many(security)
}));

export const securityRelations = relations(security, ({ many, one }) => ({
	securitiesToPortfolio: many(securitiesToPortfolios),
	type: one(securityType)
}));

export const portfolioRelations = relations(portfolio, ({ many }) => ({
	securitiesToPortfolios: many(securitiesToPortfolios)
}));

export const securitiesToPortfolios = pgTable(
	'securities_to_portfolios',
	{
		securityId: uuid('securityId')
			.notNull()
			.references(() => security.id),
		portfolioId: uuid('portfolioId')
			.notNull()
			.references(() => portfolio.id),
		weight: numeric('weight')
	},
	(table) => ({
		pk: primaryKey({ columns: [table.securityId, table.portfolioId] })
	})
);

// export const measureType = pgTable('measure_type', {
// 	id: uuid('id').defaultRandom().primaryKey(),
// 	name: text('name')
// });

// export const measure = pgTable(
// 	'measure',
// 	{
// 		securityId: text('security_id').notNull(),
// 		measureId: text('measure_id').notNull(),
// 		date: timestamp('date', { withTimezone: false }).notNull(),
// 		value: real('value')
// 	},
// 	(table) => {
// 		return {
// 			pk: primaryKey({ columns: [table.securityId, table.measureId, table.date] })
// 		};
// 	}
// );

// export const measureTypeRelations = relations(measureType, ({ many }) => ({
// 	measures: many(measure)
// }));

// export const measureRelations = relations(measure, ({ one }) => ({
// 	measureType: one(measureType, {
// 		fields: [measure.measureId],
// 		references: [measureType.id]
// 	}),
// 	security: one(security, {
// 		fields: [measure.securityId],
// 		references: [security.id]
// 	})
// }));

// export const volMethodology = pgTable('vol_methodology', {
// 	id: uuid('id').defaultRandom().primaryKey(),
// 	name: text('name')
// });

// export const quantileMethodology = pgTable('quantile_methodology', {
// 	id: uuid('id').defaultRandom(),
// 	name: text('name')
// });

// export const volModel = pgTable('vol_model', {
// 	id: uuid('id').defaultRandom().primaryKey(),
// 	name: text('name'),
// 	methodologyId: uuid('methodologyId'),
// 	params: jsonb('params')
// });

// export const quantileModel = pgTable('quantile_model', {
// 	id: uuid('id').defaultRandom().primaryKey(),
// 	name: text('name'),
// 	methodologyId: uuid('methodologyId'),
// 	params: jsonb('params')
// });

// export const volModelRelations = relations(volModel, ({ one }) => ({
// 	methodology: one(volMethodology, {
// 		fields: [volModel.methodologyId],
// 		references: [volMethodology.id]
// 	})
// }));

// export const quantileModelRelations = relations(quantileModel, ({ one }) => ({
// 	methodology: one(quantileMethodology, {
// 		fields: [quantileModel.methodologyId],
// 		references: [quantileMethodology.id]
// 	})
// }));

// export const volMethodologyRelations = relations(volMethodology, ({ many }) => ({
// 	models: many(volModel)
// }));

// export const quantileMethodologyRelations = relations(quantileMethodology, ({ many }) => ({
// 	models: many(quantileModel)
// }));

// export const varModel = pgTable('var_model', {
// 	id: uuid('id').defaultRandom().primaryKey(),
// 	name: text('name'),
// 	volModelId: uuid('volModelId'),
// 	quantileModelId: uuid('quantileModelId')
// });

// export const varModelRelations = relations(varModel, ({ one }) => ({
// 	volModel: one(volModel, {
// 		fields: [varModel.volModelId],
// 		references: [volModel.id]
// 	}),
// 	quantileModel: one(quantileModel, {
// 		fields: [varModel.quantileModelId],
// 		references: [quantileModel.id]
// 	})
// }));

export const accounts = pgTable(
	'account',
	{
		userId: text('userId')
			.notNull()
			.references(() => users.id, { onDelete: 'cascade' }),
		type: text('type').$type<AdapterAccountType>().notNull(),
		provider: text('provider').notNull(),
		providerAccountId: text('providerAccountId').notNull(),
		refresh_token: text('refresh_token'),
		access_token: text('access_token'),
		expires_at: integer('expires_at'),
		token_type: text('token_type'),
		scope: text('scope'),
		id_token: text('id_token'),
		session_state: text('session_state')
	},
	(account) => ({
		compoundKey: primaryKey({
			columns: [account.provider, account.providerAccountId]
		})
	})
);

export const sessions = pgTable('session', {
	sessionToken: text('sessionToken').primaryKey(),
	userId: text('userId')
		.notNull()
		.references(() => users.id, { onDelete: 'cascade' }),
	expires: timestamp('expires', { mode: 'date' }).notNull()
});

export const verificationTokens = pgTable(
	'verificationToken',
	{
		identifier: text('identifier').notNull(),
		token: text('token').notNull(),
		expires: timestamp('expires', { mode: 'date' }).notNull()
	},
	(verificationToken) => ({
		compositePk: primaryKey({
			columns: [verificationToken.identifier, verificationToken.token]
		})
	})
);

export const authenticators = pgTable(
	'authenticator',
	{
		credentialID: text('credentialID').notNull().unique(),
		userId: text('userId')
			.notNull()
			.references(() => users.id, { onDelete: 'cascade' }),
		providerAccountId: text('providerAccountId').notNull(),
		credentialPublicKey: text('credentialPublicKey').notNull(),
		counter: integer('counter').notNull(),
		credentialDeviceType: text('credentialDeviceType').notNull(),
		credentialBackedUp: boolean('credentialBackedUp').notNull(),
		transports: text('transports')
	},
	(authenticator) => ({
		compositePK: primaryKey({
			columns: [authenticator.userId, authenticator.credentialID]
		})
	})
);
