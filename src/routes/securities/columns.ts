import type { ColumnDef } from '@tanstack/table-core';

export type Security = {
	name: string;
	symbol: string;
	type: string;
	currency: string;
};

export const columns: ColumnDef<Security>[] = [
	{
		accessorKey: 'name',
		header: 'Name'
	},
	{
		accessorKey: 'symbol',
		header: 'Symbol'
	},
	{
		accessorKey: 'type',
		header: 'Type'
	},
	{
		accessorKey: 'currency',
		header: 'Currency'
	}
];
