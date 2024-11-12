import type { ColumnDef } from '@tanstack/table-core';

export type Security = {
	id: string;
	name: string;
	symbol: string;
};

export const columns: ColumnDef<Security>[] = [
	{
		accessorKey: 'id',
		header: 'ID'
	},
	{
		accessorKey: 'name',
		header: 'Name'
	},
	{
		accessorKey: 'symbol',
		header: 'Symbol'
	}
];
