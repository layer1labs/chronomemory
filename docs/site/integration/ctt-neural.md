# Integration — ctt-neural

[ctt-neural](https://github.com/layer1labs/ctt-neural) is the neural CTT oracle that powers chronoagent. chronomemory is used to persist benchmark results, hypotheses, and CPSC projection audit trails in a tamper-evident format — relevant for patent reduction-to-practice documentation.

## Use case 1: Benchmark results

Every benchmark run writes its results to ESDB with `kind="fact"`, `source_type="observed"`, `confidence=1.0`:

```python
from chronomemory import ChronoStore, ChronoRecord
from pathlib import Path

def record_benchmark_result(
    project_root: str,
    scenario_id: str,
    seed: int,
    model_id: str,
    result: dict,
) -> None:
    """Persist a benchmark result to ESDB with full provenance."""
    with ChronoStore(project_root, recursion_depth=0) as store:
        store.upsert(ChronoRecord(
            id=f"bench-{scenario_id}-seed{seed}",
            kind="fact",
            label=f"Scenario {scenario_id} result at seed={seed}",
            source_type="observed",
            confidence=1.0,
            evidence=[f"seed={seed}", f"model={model_id}", f"scenario={scenario_id}"],
            epistemic_boundary=[f"model:{model_id}", f"scenario:{scenario_id}"],
            data=result,
        ))
```

The tamper-evident hash chain ensures that results have not been modified after measurement — supporting §101 / §112 enablement defense for patent filings.

## Use case 2: Hypothesis tracking

Before running an experiment, record the hypothesis:

```python
store.upsert(ChronoRecord(
    id="HYP-ood-001",
    kind="hypothesis",
    label="CTTStateNet R=4→R=6 NLL gap < 5% of Bayes-optimal",
    is_hypothesis=True,
    confidence=0.75,
    source_type="inferred",
    evidence=["REQ-NN-006", "CTT-Paper §4.2"],
))
```

After the experiment, update the hypothesis to a confirmed fact:

```python
rec = store.get("HYP-ood-001")
rec.is_hypothesis = False
rec.source_type = "observed"
rec.confidence = 1.0 if gap < 0.05 else 0.0
rec.evidence.append(f"bench-B-seed42: nll_gap={measured_gap:.4f}")
store.upsert(rec)
```

## Use case 3: CPSC projection audit trail

Each CTT projection decision can be logged to prove that the CTT projection layer was the sole validity authority over all model proposals (CPSC-Specification.md §9):

```python
store.upsert(ChronoRecord(
    id=f"cpsc-projection-step{step}",
    kind="fact",
    label=f"CTT projection decision at step {step}",
    source_type="observed",
    confidence=float(result.success),
    evidence=[
        f"model={model_id}",
        f"step={step}",
        f"ctt_state_hash={state_hash}",
    ],
    data={
        "admitted": result.success,
        "violations": result.violations,
        "max_violation": result.max_violation,
    },
))
```

## Installation in ctt-neural

```toml
# pyproject.toml
[project.optional-dependencies]
esdb = [
    "chronomemory @ git+https://github.com/layer1labs/chronomemory.git",
]
```

Install with: `pip install -e ".[esdb]"`

## Querying results for analysis

```python
from chronomemory import ChronoStore

with ChronoStore("/path/to/ctt-neural") as store:
    # All confirmed benchmark results
    results = store.query(kind="fact", rag_filter=True)

    # All hypotheses (tested + untested)
    all_hyps = store.query(kind="hypothesis", status="")

    # Untested hypotheses only
    pending_hyps = [r for r in all_hyps if r.is_hypothesis]
```

## Patent support

The WAL chain provides cryptographic proof that benchmark results were not modified after measurement. `chain_valid()` should be called at the end of every experiment run and its result logged:

```python
with ChronoStore(project_root) as store:
    valid = store.chain_valid()
    print(f"Chain integrity: {valid}")
    assert valid, "Experiment results may have been tampered with!"
```
