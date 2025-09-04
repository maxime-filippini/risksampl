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

const empiricalQuantileSpec = z.object({
	type: z.literal('sample'),
	interpolation: z.nullable(z.string())
});

// Mean specifications
const sampleMeanSpec = z.object({
	type: z.literal('sample'),
	window: z.number()
});

const zeroMeanSpec = z.object({
	type: z.literal('zero')
});

const meanSpec = z.discriminatedUnion('type', [zeroMeanSpec, sampleMeanSpec]);

// Volatility specifications
const ewmaVolSpec = z.object({
	type: z.literal('EWMA'),
	decayFactor: z.number().lt(1).gt(0),
	backCastWindow: z.number()
});

const sampleVolSpec = z.object({
	type: z.literal('sample'),
	window: z.number()
});

const volSpec = z.discriminatedUnion('type', [ewmaVolSpec, sampleVolSpec]);

// Distribution specifications
const normalDistributionSpec = z.object({
	type: z.literal('normal'),
	meanSpec: meanSpec,
	volSpec: volSpec
});

const parametricQuantileSpec = z.object({
	type: z.literal('distribution'),
	distribution: z.discriminatedUnion('type', [normalDistributionSpec])
});

// Filtering is done based on a volatility and a blend parameter
export const filterSpec = z.object({
	volSpec: volSpec,
	blendParameter: z.number().gte(0).lte(1)
});

// Defining the quantile for a VaR measure is for the moment limited to:
// - Getting it from a sample, i.e. an empirical quantile
// - Getting it from a distribution specification, i.e. a parametric quantile
export const quantileSpec = z.discriminatedUnion('type', [
	empiricalQuantileSpec,
	parametricQuantileSpec
]);

export const varSpec = z.object({
	confidenceLevel: z.number().gt(0).lt(1),
	quantileSpec: quantileSpec,
	filterSpec: z.nullable(filterSpec)
});
