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
	numeric
} from 'drizzle-orm/pg-core';

export const user = pgTable('user', {
	id: uuid('id').defaultRandom().primaryKey(),
	oAuthId: text('oAuthId'),
	name: varchar('name', { length: 20 }),
	email: text('email'),
	registeredOn: timestamp('registeredOn').defaultNow()
});

export const security = pgTable('security', {
	id: uuid('id').defaultRandom().primaryKey(),
	name: text('name').notNull(),
	symbol: text('symbol').notNull()
});

export const portfolio = pgTable('portfolio', {
	id: uuid('id').defaultRandom().primaryKey(),
	name: text('name'),
	userId: uuid('userId')
		.notNull()
		.references(() => user.id, { onDelete: 'no action' })
});

export const securityRelations = relations(security, ({ many }) => ({
	securitiesToPortfolio: many(securitiesToPortfolios)
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
