- [ ] Add a VaR model schema
- [ ] Add page to browse available VaR models
- [ ] Update measures table to use VaR model IDs

How should a VaR model be structured

Historical Simulations
quantile_methodology: sample
distribution_methodology: null

Gaussian
quantile_methodology: distribution
distribution_methodology: gaussian

EWMA
quantile_methodology: distribution
distribution_methodology: ewma

FHS
filter_spec: ...
quantile_mdethodology: ...
