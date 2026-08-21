"""Testes do classificador (model.py).

Validação test-first do Motor B, no mesmo espírito do Motor A: um dataset
sintético com sinal PLANTADO (`planted_signal_dataset`, em conftest.py) —
"o modelo acha o sinal que sabemos que existe?" Não afirmamos um número
exato de acurácia (honestidade epistêmica, Seção 1 do CLAUDE.md); afirmamos
só que o modelo bate um chute aleatório de forma clara.
"""
from __future__ import annotations

import pytest

from breakout.engine_b.model import EvalResult, evaluate, train

pytestmark = pytest.mark.unit


def test_treina_e_avalia_sem_erro(planted_signal_dataset):
    X_train, X_test, y_train, y_test = planted_signal_dataset
    model = train(X_train, y_train)
    result = evaluate(model, X_test, y_test)
    assert isinstance(result, EvalResult)
    assert 0.0 <= result.accuracy <= 1.0
    assert 0.0 <= result.precision <= 1.0
    assert 0.0 <= result.recall <= 1.0
    assert result.n_test == len(y_test)
    assert result.n_positive_test == int(y_test.sum())


def test_acha_o_sinal_plantado_melhor_que_aleatorio(planted_signal_dataset):
    X_train, X_test, y_train, y_test = planted_signal_dataset
    model = train(X_train, y_train)
    result = evaluate(model, X_test, y_test)
    assert result.roc_auc > 0.6  # 0.5 = chute aleatório


def test_reproducibilidade_com_mesmo_random_state(planted_signal_dataset):
    X_train, X_test, y_train, _ = planted_signal_dataset
    m1 = train(X_train, y_train, random_state=7)
    m2 = train(X_train, y_train, random_state=7)
    assert (m1.predict(X_test) == m2.predict(X_test)).all()
