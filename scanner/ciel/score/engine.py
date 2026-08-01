"""Rubric-agnostic evaluator.

This module knows nothing about what is being measured. It reads dimensions,
signals, weights and penalties from the rubric and looks each signal up in the
registry. Swapping the rubric is a config edit; only a genuinely new *kind* of
measurement needs code, and that code goes in signals.py.

Two rules are enforced here rather than left to convention:
  1. A missing signal redistributes its weight across its siblings rather than
     scoring zero. Absent is not bad.
  2. Every contribution must carry evidence. test_scoring.py asserts it.
"""

from ..model import Contribution, Score
from . import disqualify, signals


def evaluate(company, rubric):
    metrics = company.metrics
    score = Score(rubric_version=rubric.get("rubric_version", ""))
    total = 0.0

    for dimension in rubric.get("dimensions", []):
        dim_id = dimension["id"]
        dim_weight = float(dimension.get("weight", 0))
        entries = []

        for spec in dimension.get("signals", []):
            fn = signals.REGISTRY.get(spec["id"])
            if fn is None:
                continue
            raw, scaled, evidence = fn(company, metrics)
            if scaled is None:
                continue
            entries.append((spec, raw, max(0.0, min(100.0, scaled)), evidence))

        if not entries:
            score.dimensions[dim_id] = 0.0
            continue

        # Redistribute across the signals that actually reported.
        present_weight = sum(float(s.get("weight", 0)) for s, _, _, _ in entries) or 1.0
        cap = float(dimension.get("confidence_cap", 1.0))
        dim_points = 0.0

        for spec, raw, scaled, evidence in entries:
            share = float(spec.get("weight", 0)) / present_weight
            points = (scaled / 100.0) * dim_weight * share * cap
            dim_points += points
            score.contributions.append(Contribution(
                dimension=dim_id,
                signal_id=spec["id"],
                label=spec.get("label", spec["id"]),
                raw_value=raw if raw is not None else 0.0,
                scaled=scaled,
                weight=dim_weight * share,
                points=points,
                confidence=spec.get("confidence", "high"),
                evidence=evidence,
            ))

        score.dimensions[dim_id] = dim_points
        total += dim_points

    for penalty in rubric.get("penalties", []):
        hit = disqualify.penalty_applies(penalty["id"], company, metrics)
        if hit:
            points = float(penalty.get("points", 0))
            total += points
            score.penalties.append({
                "id": penalty["id"],
                "label": penalty.get("label", penalty["id"]),
                "points": points,
                "evidence": hit,
            })

    score.total = total
    company.score = score
    return score


def rank(companies):
    """Sort by score, then by what we know, then by name for stability."""
    return sorted(
        companies,
        key=lambda c: (
            -(c.score.total if c.score else -999),
            -(c.metrics.get("field_completeness") or 0),
            c.name or "",
        ),
    )
