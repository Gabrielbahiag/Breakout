"""Testes da definição de "viral" (label.py).

`label_by_threshold` e `label_by_percentile` são testados com exemplos à mão
(a resposta certa tem que ser óbvia), igual a `test_metrics.py`. As
propriedades contra os arquétipos sintéticos garantem que a defesa contra
viés de seleção (devolver `None` em vez de `False` prematuro) se comporta
como esperado em curvas realistas, não só em exemplos artificiais.
"""
from __future__ import annotations

import numpy as np
import pytest

from breakout.engine_b.label import label_by_percentile, label_by_threshold
from breakout.synth.trajectories import make_trajectory
from breakout.types import Archetype, Trajectory

pytestmark = pytest.mark.unit


def _traj(video_id: str, views: list[int]) -> Trajectory:
    t = np.arange(len(views), dtype=float)
    return Trajectory(video_id, t, np.array(views, dtype=np.int64))


# ---- label_by_threshold ---------------------------------------------------


def test_true_quando_ja_cruzou_o_limiar_mesmo_recem_observado():
    traj = _traj("v1", [0, 50, 120])  # cruza 100 em t=2, só 2h observadas
    assert label_by_threshold(traj, threshold=100, min_observed_hours=24) is True


def test_none_quando_nao_cruzou_e_ainda_nao_deu_tempo():
    traj = _traj("v1", [0, 5, 10])  # 2h observadas, nunca cruza 100
    assert label_by_threshold(traj, threshold=100, min_observed_hours=24) is None


def test_false_quando_nao_cruzou_apos_tempo_suficiente():
    traj = _traj("v1", [0, 5, 10])  # 2h observadas
    assert label_by_threshold(traj, threshold=100, min_observed_hours=2) is False


def test_borda_exatamente_no_min_observed_hours_conta_como_observado():
    traj = _traj("v1", [0, 5, 10])  # última hora observada = 2.0
    assert label_by_threshold(traj, threshold=100, min_observed_hours=2.0) is False


@pytest.mark.parametrize("archetype", [Archetype.ROCKET, Archetype.SLEEPER, Archetype.SLOW_BURN])
def test_arquetipos_que_viralizam_dao_true_mesmo_com_min_observed_alto(archetype):
    traj, truth = make_trajectory(archetype, seed=3)
    assert truth.is_viral  # pré-condição do teste
    label = label_by_threshold(traj, threshold=100_000, min_observed_hours=10_000.0)
    assert label is True


def test_stillborn_da_false_apos_observado_o_suficiente():
    traj, truth = make_trajectory(Archetype.STILLBORN, seed=3)
    assert not truth.is_viral  # pré-condição do teste
    label = label_by_threshold(traj, threshold=100_000, min_observed_hours=1.0)
    assert label is False


def test_stillborn_da_none_se_observado_por_pouco_tempo():
    traj, _ = make_trajectory(Archetype.STILLBORN, seed=3)
    label = label_by_threshold(traj, threshold=100_000, min_observed_hours=10_000.0)
    assert label is None


# ---- label_by_percentile ---------------------------------------------------


def test_percentile_marca_o_topo_do_grupo():
    trajs = [_traj("baixo", [10]), _traj("medio", [50]), _traj("alto", [1000])]
    labels = label_by_percentile(trajs, top_percent=34)  # ~1 de 3
    assert labels == {"baixo": False, "medio": False, "alto": True}


def test_percentile_grupo_vazio():
    assert label_by_percentile([], top_percent=10) == {}


def test_percentile_grupo_de_um_e_sempre_topo():
    trajs = [_traj("sozinho", [42])]
    assert label_by_percentile(trajs, top_percent=1) == {"sozinho": True}
