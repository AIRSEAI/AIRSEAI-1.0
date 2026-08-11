# Minimal semantic-contract example

Run:

```bash
python3 sample.py
```

It checks the legality distinction used by the paper: scan state is scan-local,
the observation condition may be reused through the policy lifetime, and
episode-level persistence of both is illegal in the Mamba Policy instance.
This example illustrates the semantic interface; it is not the historical
Part-III performance cost model.
