"""Bake-off dos detectores do Motor A — a razão de ser do Protocol `Detector`.

Roda a MESMA bateria de trajetórias (verdade conhecida, `synth.make_batch`) por
vários detectores intercambiáveis e resume duas coisas distintas de propósito:

  - **Alarme (precisão/recall):** positivo = arquétipo tem decolagem verdadeira
    (`truth.takeoff_hours is not None`). Isso mede se o detector acha o change
    point que existe, não se o vídeo "vira" — ROCKET/SLOW_BURN/SLEEPER/
    FLASH_IN_PAN decolam; só STILLBORN não.
  - **Earliness (lead time):** só faz sentido para quem de fato CRUZA o limiar
    de viral (`crossing_hours`) — um vídeo que decola mas nunca viraliza
    (FLASH_IN_PAN abaixo do limiar) não tem "quanto antes" medir.

As duas métricas usam o MESMO `threshold` passado aqui — nunca o que foi usado
lá na geração do batch (evita a pegadinha de misturar limiares diferentes).
"""
from __future__ import annotations

import dataclasses

import pandas as pd

from ..contracts import Detector
from ..types import GroundTruth, Trajectory
from .metrics import lead_time_hours
from .replay import run_detector


@dataclasses.dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Resumo de um detector sobre uma bateria de trajetórias."""

    detector: str
    n: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    mean_lead_time_hours: float | None
    median_lead_time_hours: float | None


def evaluate_detector(
    detector: Detector,
    batch: list[tuple[Trajectory, GroundTruth]],
    threshold: int,
) -> BenchmarkResult:
    """Roda `detector` sobre `batch` e resume acerto de alarme + earliness."""
    tp = fp = fn = tn = 0
    lead_times: list[float] = []

    for traj, truth in batch:
        hit = run_detector(detector, traj)
        fired = hit is not None
        real_takeoff = truth.takeoff_hours is not None

        if fired and real_takeoff:
            tp += 1
        elif fired and not real_takeoff:
            fp += 1
        elif not fired and real_takeoff:
            fn += 1
        else:
            tn += 1

        lt = lead_time_hours(hit, traj, threshold)
        if lt is not None:
            lead_times.append(lt)

    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    lt_series = pd.Series(lead_times, dtype=float)

    return BenchmarkResult(
        detector=detector.name,
        n=len(batch),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        precision=precision,
        recall=recall,
        mean_lead_time_hours=float(lt_series.mean()) if len(lt_series) else None,
        median_lead_time_hours=float(lt_series.median()) if len(lt_series) else None,
    )


def bakeoff(
    detectors: list[Detector],
    batch: list[tuple[Trajectory, GroundTruth]],
    threshold: int,
) -> pd.DataFrame:
    """Roda vários detectores sobre a MESMA bateria — uma linha por detector."""
    rows = [evaluate_detector(d, batch, threshold) for d in detectors]
    return pd.DataFrame([dataclasses.asdict(r) for r in rows])
