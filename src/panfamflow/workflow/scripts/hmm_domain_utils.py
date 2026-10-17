"""Transparent coverage metrics for an individual HMMER domtblout domain hit."""

from __future__ import annotations

from collections.abc import Sequence


def hmm_model_span(fields: Sequence[str]) -> dict[str, int | float]:
    """Return model-coordinate coverage for one HMMER ``--domtblout`` row.

    Columns 6, 16 and 17 (1-based) are HMM query length/from/to when
    ``hmmsearch`` searches a sequence database. The metric describes only
    the *single reported domain hit*. It is neither whole-protein length
    coverage nor independent proof that the biological domain is intact.
    """
    if len(fields) < 22:
        raise ValueError("HMMER domtblout row has fewer than 22 fields")
    model_length = int(fields[5])
    model_from = int(fields[15])
    model_to = int(fields[16])
    if model_length < 1 or not 1 <= model_from <= model_to <= model_length:
        raise ValueError(
            "Invalid HMM model-coordinate interval "
            f"{model_from}-{model_to} of {model_length}"
        )
    return {
        "hmm_model_length": model_length,
        "hmm_model_from": model_from,
        "hmm_model_to": model_to,
        "hmm_model_coverage": (model_to - model_from + 1) / model_length,
    }
