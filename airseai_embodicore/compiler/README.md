# Compiler layer

`reference_semantic_filter.py` is a compact reference implementation of the
EmbodiCore **semantic legality interface**. It demonstrates that lifetime/
reset/reuse decisions that appear legal under storage-liveness reasoning can
be rejected once physical-loop execution events are introduced.

It is **not** the original historical Part-III DSE implementation and does not
reconstruct the missing cost model, candidate generator, or objective ranking.
The original Part-III source was not recovered into this release.
