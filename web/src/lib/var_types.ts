import z from 'zod';

type SampleFilterSpec = {
	type: 'sample';
	window: number;
};

type EwmaSpec = {
	decayFactor: number;
	backcastWindow: number;
};

type EwmaFilterSpec = {
	type: 'ewma';
	spec: EwmaSpec;
};

export type FilterSpec = SampleFilterSpec | EwmaFilterSpec;

type SampleQuantileSpec = {
	type: 'sample';
	interpolation: string | null;
};

type DistributionSpec = 'normal' | 't';

type DistributionQuantileSpec = {
	type: 'distribution';
	distribution: DistributionSpec;
};

type QuantileSpec = SampleQuantileSpec | DistributionQuantileSpec;

export type VarSpec = {
	confidenceLevel: number;
	quantileSpec: QuantileSpec;
	filterSpec: FilterSpec | null;
};

const sampleFilterSpec = z.object({
	type: z.literal('sample'),
	window: z.int()
});

const ewmaSpec = z.object({
	decayFactor: z.number().lt(1).gt(0)
});

const ewmaFilterSpec = z.object({
	type: z.literal('ewma'),
	spec: ewmaSpec
});

export const filterSpec = z.discriminatedUnion('kind', [sampleFilterSpec, ewmaFilterSpec]);
