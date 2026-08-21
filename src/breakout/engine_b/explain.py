"""Explicação do modelo (SHAP) — o "por quê" do Motor B.

Honestidade epistêmica (Seção 1 do CLAUDE.md): isto explica o MODELO, não o
FENÔMENO — "correlato", nunca "causa". `TreeExplainer` é exato e rápido pra
Random Forest (não precisa da aproximação genérica do `KernelExplainer`).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import RandomForestClassifier


def shap_values(model: RandomForestClassifier, X: pd.DataFrame) -> pd.DataFrame:
    """SHAP value de cada feature, por linha de `X` — mesmo shape de `X`.

    Sempre a contribuição pra classe POSITIVA (viral=True). A forma exata que
    `TreeExplainer.shap_values` devolve varia entre versões do shap (lista
    por classe nas mais antigas; ndarray `(n, features, classes)` nas
    recentes) — trata os dois formatos.
    """
    explainer = shap.TreeExplainer(model)
    raw = explainer.shap_values(X)

    if isinstance(raw, list):
        values = raw[1]  # [classe_negativa, classe_positiva]
    elif raw.ndim == 3:
        values = raw[:, :, 1]
    else:
        values = raw

    return pd.DataFrame(np.asarray(values), columns=X.columns, index=X.index)


def feature_importance(model: RandomForestClassifier, X: pd.DataFrame) -> pd.Series:
    """Importância GLOBAL: média do |SHAP value| por feature, da mais pra
    menos importante — "quais elementos se correlacionam com viralizar"."""
    return shap_values(model, X).abs().mean().sort_values(ascending=False)
