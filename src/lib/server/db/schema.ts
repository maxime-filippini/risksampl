import { relations } from 'drizzle-orm';
import { sqliteTable, text, real, primaryKey } from 'drizzle-orm/sqlite-core';
import { v4 as uuidv4 } from 'uuid';

export const user = sqliteTable('user', {
	id: text('id').$defaultFn(uuidv4).primaryKey(),
	name: text('name')
});

export const security = sqliteTable('security', {
	id: text('id').$defaultFn(uuidv4).primaryKey(),
	name: text('name'),
	symbol: text('name')
});

export const measureType = sqliteTable('measure_type', {
	id: text('id').$defaultFn(uuidv4).primaryKey(),
	name: text('name')
});

export const measure = sqliteTable(
	'measure',
	{
		securityId: text('security_id'),
		measureId: text('measure_id'),
		date: text('date'),
		value: real('value')
	},
	(table) => {
		return {
			pk: primaryKey({ columns: [table.securityId, table.measureId, table.date] })
		};
	}
);

export const measureTypeRelations = relations(measureType, ({ many }) => ({
	measures: many(measure)
}));

export const measureRelations = relations(measure, ({ one }) => ({
	measureType: one(measureType, {
		fields: [measure.measureId],
		references: [measureType.id]
	}),
	security: one(security, {
		fields: [measure.securityId],
		references: [security.id]
	})
}));

export const varMethodologies = sqliteTable('var_methodologies', {
	id: text('id').$defaultFn(uuidv4).primaryKey(),
	name: text('id')
});

export const varModels = sqliteTable('var_models', {
	id: text('id').$defaultFn(uuidv4).primaryKey(),
	name: text('name'),
	methodologiesId: text('methodologiesId').references(() => varMethodologies.id)
});
