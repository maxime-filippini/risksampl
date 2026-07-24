import type { VarSpec } from '$lib/var_types';
import { relations, sql } from 'drizzle-orm';
import {
	pgTable,
	varchar,
	index,
	uniqueIndex,
	unique,
	uuid,
	foreignKey,
	primaryKey,
	date,
	numeric,
	decimal,
	boolean,
	check,
	pgEnum,
	jsonb
} from 'drizzle-orm/pg-core';

export const instruments = pgTable(
	'instruments',
	{
		id: uuid().primaryKey().notNull(),
		name: varchar({ length: 255 }).notNull(),
		ticker: varchar({ length: 10 }).notNull(),
		providerSymbol: varchar('provider_symbol', { length: 32 }),
		exchangeCode: varchar('exchange_code', { length: 16 }),
		currency: varchar({ length: 3 }).notNull(),
		assetClass: varchar({ length: 50 }).notNull(),
		enabled: boolean().default(false).notNull(),
		catchUpRequired: boolean('catch_up_required').default(false).notNull(),
		firstValidatedObservationDate: date('first_validated_observation_date'),
		latestValidatedObservationDate: date('latest_validated_observation_date')
	},
	(table) => [
		index('ix_instruments_id').using('btree', table.id.asc().nullsLast().op('uuid_ops')),
		uniqueIndex('ix_instruments_ticker').using(
			'btree',
			table.ticker.asc().nullsLast().op('text_ops')
		),
		uniqueIndex('ix_instruments_provider_identity').on(table.providerSymbol, table.exchangeCode),
		check(
			'instruments_provider_identity_complete',
			sql`(${table.providerSymbol} IS NULL) = (${table.exchangeCode} IS NULL)`
		),
		check(
			'instruments_validated_coverage_complete',
			sql`((${table.firstValidatedObservationDate} IS NULL) = (${table.latestValidatedObservationDate} IS NULL))
				AND (${table.firstValidatedObservationDate} IS NULL OR ${table.firstValidatedObservationDate} <= ${table.latestValidatedObservationDate})`
		),
		check(
			'instruments_enabled_state_complete',
			sql`NOT ${table.enabled} OR (
				${table.providerSymbol} IS NOT NULL
				AND ${table.exchangeCode} IS NOT NULL
				AND ${table.firstValidatedObservationDate} IS NOT NULL
				AND ${table.latestValidatedObservationDate} IS NOT NULL
				AND NOT ${table.catchUpRequired}
			)`
		),
		unique('instruments_name_key').on(table.name)
	]
);

export const portfolios = pgTable(
	'portfolios',
	{
		id: uuid().primaryKey().notNull(),
		name: varchar({ length: 100 }).notNull(),
		currency: varchar({ length: 3 }).notNull(),
		assetClass: varchar({ length: 50 }).notNull()
	},
	(table) => [
		index('ix_portfolios_id').using('btree', table.id.asc().nullsLast().op('uuid_ops')),
		unique('portfolios_name_key').on(table.name)
	]
);

export const investments = pgTable(
	'investments',
	{
		id: uuid().primaryKey().notNull(),
		date: date().notNull(),
		portfolioId: uuid('portfolio_id').notNull(),
		instrumentId: uuid('instrument_id').notNull(),
		quantity: numeric({ precision: 20, scale: 8 }).notNull()
	},
	(table) => [
		foreignKey({
			columns: [table.instrumentId],
			foreignColumns: [instruments.id],
			name: 'investments_instrument_id_fkey'
		}).onDelete('cascade'),
		foreignKey({
			columns: [table.portfolioId],
			foreignColumns: [portfolios.id],
			name: 'investments_portfolio_id_fkey'
		}).onDelete('cascade'),
		index('ix_investments_date').using('btree', table.date.asc().nullsLast()),
		index('ix_investments_portfolio').using(
			'btree',
			table.portfolioId.asc().nullsLast().op('uuid_ops')
		)
	]
);

export const investmentsRelations = relations(investments, ({ one }) => ({
	instrument: one(instruments, {
		fields: [investments.instrumentId],
		references: [instruments.id]
	}),
	portfolio: one(portfolios, {
		fields: [investments.portfolioId],
		references: [portfolios.id]
	})
}));

export const instrumentsRelations = relations(instruments, ({ many }) => ({
	investments: many(investments)
}));

export const portfoliosRelations = relations(portfolios, ({ many }) => ({
	investments: many(investments)
}));

export const RequestsTable = pgTable('requests', {
	id: uuid().primaryKey().notNull(),
	email: varchar({ length: 255 }).notNull(),
	request: varchar({ length: 10000 }).notNull()
});

export const MarketDataTable = pgTable(
	'market_data',
	{
		instrumentId: uuid('instrument_id').notNull(),
		date: date().notNull(),
		data_type: varchar({ length: 50 }),
		value: decimal()
	},
	(table) => [
		foreignKey({
			columns: [table.instrumentId],
			foreignColumns: [instruments.id],
			name: 'instrument_id_fkey'
		}).onDelete('cascade'),
		primaryKey({
			columns: [table.instrumentId, table.date, table.data_type],
			name: 'market_data_pkey'
		})
	]
);

export const PortfolioValueTable = pgTable(
	'ptf_values',
	{
		date: date().notNull(),
		portfolioId: uuid('portfolio_id').notNull(),
		value: numeric({ precision: 20, scale: 8 }).notNull()
	},
	(table) => [
		foreignKey({
			columns: [table.portfolioId],
			foreignColumns: [portfolios.id],
			name: 'portfolio_id_fkey'
		}).onDelete('cascade'),
		primaryKey({
			columns: [table.portfolioId, table.date],
			name: 'ptf_values_pkey'
		})
	]
);

export const PortfolioCompositionTable = pgTable(
	'ptf_comp',
	{
		date: date().notNull(),
		portfolioId: uuid('portfolio_id').notNull(),
		instrumentId: uuid('instrument_id').notNull(),
		quantity: numeric({ precision: 20, scale: 8 }).notNull()
	},
	(table) => [
		foreignKey({
			columns: [table.portfolioId],
			foreignColumns: [portfolios.id],
			name: 'ptf_comp_portfolio_id_fkey'
		}).onDelete('cascade'),
		foreignKey({
			columns: [table.instrumentId],
			foreignColumns: [instruments.id],
			name: 'ptf_comp_instrument_id_fkey'
		}).onDelete('cascade'),
		primaryKey({
			columns: [table.instrumentId, table.portfolioId, table.date],
			name: 'ptf_comp_pkey'
		})
	]
);

export const MeasurementsTable = pgTable(
	'measurements',
	{
		portfolioId: uuid('portfolio_id').notNull(),
		date: date().notNull(),
		measure: varchar({ length: 200 }),
		value: decimal()
	},
	(table) => [
		foreignKey({
			columns: [table.portfolioId],
			foreignColumns: [portfolios.id],
			name: 'measures_portfolio_id_fkey'
		}).onDelete('cascade'),
		foreignKey({
			columns: [table.measure],
			foreignColumns: [MeasuresTable.id],
			name: 'measures_measure_fkey'
		}).onDelete('cascade'),
		primaryKey({
			columns: [table.portfolioId, table.date, table.measure],
			name: 'measures_pkey'
		})
	]
);

export const dateTypeEnum = pgEnum('date_type', ['current', 'history']);

export const DatesTable = pgTable('dates', {
	date: date().primaryKey().notNull(),
	type: dateTypeEnum().notNull()
});

export const VarModelTable = pgTable('var_models', {
	id: varchar({ length: 200 }).primaryKey(),
	name: varchar({ length: 200 }),
	spec: jsonb().$type<VarSpec>()
});

export const measureType = pgEnum('measure_type', ['value_at_risk', 'other']);

export const MeasuresTable = pgTable('measures', {
	id: varchar({ length: 200 }).primaryKey(),
	name: varchar({ length: 200 }).notNull(),
	type: measureType().notNull(),
	spec: jsonb()
});
