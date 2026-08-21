"""Testes de explicação (explain.py).

A propriedade central: sobre o dataset com sinal PLANTADO
(`planted_signal_dataset`), o SHAP tem que apontar a feature que SABEMOS que
importa (`title_has_number`) acima das features de ruído — "o modelo explica
o sinal que sabemos que está lá?"
"""
from __future__ import annotations

import pytest

from breakout.engine_b.explain import feature_importance, shap_values
from breakout.engine_b.model import train

pytestmark = pytest.mark.unit


def test_shap_values_mesmo_shape_de_x(planted_signal_dataset):
    X_train, X_test, y_train, _ = planted_signal_dataset
    model = train(X_train, y_train)
    sv = shap_values(model, X_test)
    assert sv.shape == X_test.shape
    assert list(sv.columns) == list(X_test.columns)


def test_feature_importance_acha_o_sinal_plantado(planted_signal_dataset):
    X_train, X_test, y_train, _ = planted_signal_dataset
    model = train(X_train, y_train)
    importance = feature_importance(model, X_test)
    assert importance.index[0] == "title_has_number"
