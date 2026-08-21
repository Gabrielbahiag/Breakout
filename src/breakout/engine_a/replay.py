"""Harness de replay: roda um detector ONLINE sobre uma trajetória, como se os
pontos chegassem ao vivo. É teste e feature ao mesmo tempo — é exatamente o
"modo simulação" que a gente quer no dashboard/README (ver a decolagem disparar
no instante certo).
"""
from __future__ import annotations

from ..contracts import Detector
from ..types import Detection, Trajectory


def run_detector(detector: Detector, trajectory: Trajectory) -> Detection | None:
    """Reproduz a trajetória no detector e devolve a PRIMEIRA detecção (semântica
    de detecção precoce: a gente quer o alarme mais cedo possível), ou None se
    nunca disparou."""
    detector.reset()
    for t, v in trajectory.stream():
        hit = detector.update(t, v)
        if hit is not None:
            return hit
    return None


def run_detector_all(detector: Detector, trajectory: Trajectory) -> list[Detection]:
    """Todas as detecções ao longo da trajetória (útil para diagnosticar
    re-disparos e para o dashboard)."""
    detector.reset()
    hits: list[Detection] = []
    for t, v in trajectory.stream():
        hit = detector.update(t, v)
        if hit is not None:
            hits.append(hit)
    return hits
