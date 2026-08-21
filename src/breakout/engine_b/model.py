"""Classificador viral/não-viral — o modelo do Motor B.

Random Forest: robusto a features de escalas bem diferentes sem normalização
(`views_per_hour` pode ser 10 ou 100.000; `title_length` é sempre <100), e tem
suporte NATIVO e EXATO no SHAP (`TreeExplainer`) — ao contrário de modelos
genéricos, que só têm aproximação (`KernelExplainer`, lento e instável).

Honestidade epistêmica (Seção 1 do CLAUDE.md): "viral" é parte efeito de rede
e sorte, então o teto de acurácia é honestamente baixo — nunca reportar só
`accuracy` (a classe viral é minoritária por construção; um modelo que chuta
"não viral" sempre já acerta a maioria e engana). `evaluate` sempre devolve
precision/recall/ROC-AUC junto.
"""
from __future__ import annotations

import dataclasses

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score


@dataclasses.dataclass(frozen=True, slots=True)
class EvalResult:
    """Métricas honestas sobre um conjunto de teste."""

    accuracy: float
    precision: float
    recall: float
    roc_auc: float
    n_test: int
    n_positive_test: int


def train(X: pd.DataFrame, y: pd.Series, *, random_state: int = 0) -> RandomForestClassifier:
    """Treina o classificador. `class_weight="balanced"` compensa a classe
    viral minoritária; `random_state` fixo é reprodutibilidade, não é
    reivindicação de hiperparâmetro ótimo."""
    model = RandomForestClassifier(n_estimators=200, random_state=random_state, class_weight="balanced")
    model.fit(X, y)
    return model


def evaluate(model: RandomForestClassifier, X_test: pd.DataFrame, y_test: pd.Series) -> EvalResult:
    """Resume o desempenho em cima de um conjunto de teste NÃO visto no treino."""
    pred = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]
    has_both_classes = y_test.nunique() > 1
    return EvalResult(
        accuracy=float(accuracy_score(y_test, pred)),
        precision=float(precision_score(y_test, pred, zero_division=0)),
        recall=float(recall_score(y_test, pred, zero_division=0)),
        roc_auc=float(roc_auc_score(y_test, proba)) if has_both_classes else float("nan"),
        n_test=len(y_test),
        n_positive_test=int(y_test.sum()),
    )
