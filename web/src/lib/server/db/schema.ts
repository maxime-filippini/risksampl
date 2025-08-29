import { relations } from 'drizzle-orm';
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
	decimal
} from 'drizzle-orm/pg-core';

export const alembicVersion = pgTable('alembic_version', {
	versionNum: varchar('version_num', { length: 32 }).primaryKey().notNull()
});

export const instruments = pgTable(
	'instruments',
	{
		id: uuid().primaryKey().notNull(),
		name: varchar({ length: 255 }).notNull(),
		ticker: varchar({ length: 10 }).notNull(),
		currency: varchar({ length: 3 }).notNull()
	},
	(table) => [
		index('ix_instruments_id').using('btree', table.id.asc().nullsLast().op('uuid_ops')),
		uniqueIndex('ix_instruments_ticker').using(
			'btree',
			table.ticker.asc().nullsLast().op('text_ops')
		),
		unique('instruments_name_key').on(table.name)
	]
);

export const portfolios = pgTable(
	'portfolios',
	{
		id: uuid().primaryKey().notNull(),
		name: varchar({ length: 100 }).notNull(),
		currency: varchar({ length: 3 }).notNull()
	},
	(table) => [
		index('ix_portfolios_id').using('btree', table.id.asc().nullsLast().op('uuid_ops')),
		unique('portfolios_name_key').on(table.name)
	]
);

export const holdings = pgTable(
	'holdings',
	{
		asOf: date('as_of').notNull(),
		portfolioId: uuid('portfolio_id').notNull(),
		instrumentId: uuid('instrument_id').notNull(),
		quantity: numeric({ precision: 20, scale: 8 }).notNull()
	},
	(table) => [
		foreignKey({
			columns: [table.instrumentId],
			foreignColumns: [instruments.id],
			name: 'holdings_instrument_id_fkey'
		}).onDelete('cascade'),
		foreignKey({
			columns: [table.portfolioId],
			foreignColumns: [portfolios.id],
			name: 'holdings_portfolio_id_fkey'
		}).onDelete('cascade'),
		primaryKey({
			columns: [table.asOf, table.portfolioId, table.instrumentId],
			name: 'holdings_pkey'
		})
	]
);

export const holdingsRelations = relations(holdings, ({ one }) => ({
	instrument: one(instruments, {
		fields: [holdings.instrumentId],
		references: [instruments.id]
	}),
	portfolio: one(portfolios, {
		fields: [holdings.portfolioId],
		references: [portfolios.id]
	})
}));

export const instrumentsRelations = relations(instruments, ({ many }) => ({
	holdings: many(holdings)
}));

export const portfoliosRelations = relations(portfolios, ({ many }) => ({
	holdings: many(holdings)
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
			name: 'pkey'
		})
	]
);
