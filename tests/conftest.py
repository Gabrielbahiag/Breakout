"""Fixtures compartilhados da suíte Breakout.

Aqui moram as peças de teste reutilizáveis: os fakes (relógio, storage, API), um
gerador aleatório com seed fixa (reprodutibilidade) e uma fábrica de trajetórias
sintéticas. Um teste pede o que precisa por nome de argumento.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from breakout.synth.trajectories import make_trajectory
from breakout.types import Archetype
from tests.fakes.clock import ManualClock
from tests.fakes.repository import InMemoryTrajectoryRepository
from tests.fakes.youtube import FakeYouTubeClient

# Seed global para qualquer aleatoriedade não coberta por fixture explícita.
_SEED = 20260820


@pytest.fixture
def rng() -> np.random.Generator:
    """Gerador numpy com seed fixa — nada de teste 'flaky' por acaso."""
    return np.random.default_rng(_SEED)


@pytest.fixture
def manual_clock() -> ManualClock:
    return ManualClock(datetime(2026, 1, 1, tzinfo=timezone.utc))


@pytest.fixture
def repo() -> InMemoryTrajectoryRepository:
    return InMemoryTrajectoryRepository()


@pytest.fixture
def fake_youtube() -> FakeYouTubeClient:
    return FakeYouTubeClient()


@pytest.fixture
def make_traj():
    """Fábrica de trajetórias sintéticas. Uso:

        traj, truth = make_traj(Archetype.ROCKET, seed=1)
    """
    def _factory(archetype: Archetype, **kwargs):
        return make_trajectory(archetype, **kwargs)

    return _factory


@pytest.fixture(params=list(Archetype), ids=lambda a: a.value)
def any_archetype(request) -> Archetype:
    """Parametriza um teste sobre TODOS os arquétipos de uma vez."""
    return request.param
