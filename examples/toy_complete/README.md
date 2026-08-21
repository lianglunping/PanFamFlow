# PanFamFlow complete synthetic fixture

This directory contains deterministic synthetic inputs only. It exercises every
PanFamFlow module and every optional complete-profile path, but it is not
biological evidence and must not be used for biological interpretation.

- Scope: `TOY_ENGINEERING_ONLY`
- Seed: `20260821`
- Expected runtime host: Kunpeng HPC with the frozen PanFamFlow engine
- Expected outputs: generated under `results/`, `work/`, and `logs/` at run time

Regenerate the fixture from the repository root with:

```bash
uv run python scripts/generate_toy_complete.py
```
