"""Fixtures compartilhados da suíte Breakout.

Aqui moram as peças de teste reutilizáveis: os fakes (relógio, storage, API), um
gerador aleatório com seed fixa (reprodutibilidade) e uma fábrica de trajetórias
sintéticas. Um teste pede o que precisa por nome de argumento.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import train_test_split

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


@pytest.fixture
def planted_signal_dataset():
    """Dataset sintético do Motor B com um sinal PLANTADO conhecido: título
    com número triplica a chance de viralizar, por construção. Mesmo truque
    das trajetórias sintéticas do Motor A, aplicado a model.py/explain.py —
    "o modelo/SHAP acha o sinal que sabemos que está lá?" Devolve
    (X_train, X_test, y_train, y_test)."""
    rng = np.random.default_rng(_SEED)
    n = 400
    has_number = rng.integers(0, 2, size=n).astype(float)
    base_prob = 0.15
    prob = np.where(has_number > 0, base_prob * 3, base_prob)
    is_viral = (rng.random(n) < prob).astype(int)
    X = pd.DataFrame(
        {
            "title_has_number": has_number,
            "noise_a": rng.normal(size=n),
            "noise_b": rng.normal(size=n),
        }
    )
    y = pd.Series(is_viral, name="is_viral")
    return train_test_split(X, y, test_size=0.3, random_state=0, stratify=y)
