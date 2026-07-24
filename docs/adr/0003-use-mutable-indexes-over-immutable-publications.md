# Use mutable indexes over immutable publications

Small discovery indexes may be updated to identify the authoritative revision
for each as-of date and the latest available publication. All publication
revisions, manifests, inputs, and results remain immutable. This makes
supersession explicit and fast to read while keeping the mutable state
rebuildable entirely from immutable manifests.
