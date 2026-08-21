"""Testes do bake-off (benchmark.py).

Aqui testamos a ARITMÉTICA do benchmark (matriz de confusão, agregação), não a
qualidade de nenhum detector — por isso usamos detectores-fake determinísticos
(sempre dispara / nunca dispara), não os reais. Igual a test_metrics.py: a
resposta certa tem que ser óbvia à mão.
"""
from __future__ import annotations

import math

import pytest

from breakout.engine_a.baseline import BaselineDetector
from breakout.engine_a.benchmark import bakeoff, evaluate_detector, sensitivity_curve
from breakout.engine_a.changepoint import CusumDetector
from breakout.synth.trajectories import VIRAL_THRESHOLD_DEFAULT, make_batch
from breakout.types import Detection

pytestmark = pytest.mark.unit


class _NuncaDispara:
    name = "nunca"

    def update(self, t_hours: float, views: float) -> Detection | None:
        return None

    def reset(self) -> None:
        pass


class _SempreDispara:
    """Dispara no segundo ponto de qualquer trajetória (a 1a taxa observável)."""

    name = "sempre"

    def __init__(self) -> None:
        self._n = 0

    def update(self, t_hours: float, views: float) -> Detection | None:
        self._n += 1
        if self._n == 2:
            return Detection(detector=self.name, at_hours=t_hours, score=1.0)
        return None

    def reset(self) -> None:
        self._n = 0


# 5 arquétipos x 3 = 15 trajetórias; só STILLBORN não tem decolagem verdadeira
# (4 arquétipos decolam x 3 = 12 com takeoff, 1 x 3 = 3 sem).
_BATCH = make_batch(per_archetype=3, base_seed=0)
_N_COM_TAKEOFF = 12
_N_SEM_TAKEOFF = 3


def test_matriz_de_confusao_soma_para_n():
    result = evaluate_detector(BaselineDetector(), _BATCH, threshold=VIRAL_THRESHOLD_DEFAULT)
    total = result.true_positives + result.false_positives + result.false_negatives + result.true_negatives
    assert total == len(_BATCH) == result.n


def test_detector_que_nunca_dispara_so_produz_fn_e_tn():
    result = evaluate_detector(_NuncaDispara(), _BATCH, threshold=VIRAL_THRESHOLD_DEFAULT)
    assert result.true_positives == 0
    assert result.false_positives == 0
    assert result.false_negatives == _N_COM_TAKEOFF
    assert result.true_negatives == _N_SEM_TAKEOFF
    assert result.recall == 0.0
    assert math.isnan(result.precision)          # 0/0: não disparou nenhuma vez
    assert result.mean_lead_time_hours is None    # nunca detectou nada


def test_detector_que_sempre_dispara_so_produz_tp_e_fp():
    result = evaluate_detector(_SempreDispara(), _BATCH, threshold=VIRAL_THRESHOLD_DEFAULT)
    assert result.true_positives == _N_COM_TAKEOFF
    assert result.false_positives == _N_SEM_TAKEOFF
    assert result.false_negatives == 0
    assert result.true_negatives == 0
    assert result.recall == 1.0
    assert result.precision == pytest.approx(_N_COM_TAKEOFF / len(_BATCH))


def test_bakeoff_retorna_uma_linha_por_detector():
    df = bakeoff(
        [BaselineDetector(), CusumDetector()],
        _BATCH,
        threshold=VIRAL_THRESHOLD_DEFAULT,
    )
    assert len(df) == 2
    assert set(df["detector"]) == {"baseline_accel", "cusum"}
    assert (df["n"] == len(_BATCH)).all()


def test_sensitivity_curve_retorna_uma_linha_por_valor_de_parametro():
    values = [500, 3000, 12000]
    df = sensitivity_curve(
        lambda th: CusumDetector(threshold=th),
        values,
        _BATCH,
        threshold=VIRAL_THRESHOLD_DEFAULT,
    )
    assert list(df["param_value"]) == values
    assert (df["detector"] == "cusum").all()


def test_sensitivity_curve_expoe_o_trade_off_earliness_x_acuracia():
    # threshold do CUSUM mais alto = mais conservador = dispara mais tarde
    # (earliness cai) e perde mais casos (recall cai) — o trade-off central
    # do Motor A (Seção 6 do CLAUDE.md), visível na mesma bateria.
    values = [500, 1000, 2000, 3000, 5000, 8000, 12000]
    df = sensitivity_curve(
        lambda th: CusumDetector(threshold=th),
        values,
        _BATCH,
        threshold=VIRAL_THRESHOLD_DEFAULT,
    )
    lead = df["mean_lead_time_hours"].tolist()
    assert all(a >= b for a, b in zip(lead, lead[1:]))  # não-crescente
    assert lead[0] > lead[-1]                            # trade-off de fato existe
    assert df["recall"].iloc[0] >= df["recall"].iloc[-1]
