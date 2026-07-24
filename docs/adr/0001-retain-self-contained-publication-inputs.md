# Retain self-contained inputs for every publication

Each VaR Labs publication retains a complete immutable normalized market-data
input snapshot and references it from the publication record. This deliberately
duplicates a small amount of market data, but guarantees that a historical
result can be reproduced from retained objects even if the provider’s history
changes or VaR Labs later corrects an observation.
