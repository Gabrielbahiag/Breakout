"""Definição de "viral" — o rótulo do Motor B.

A Seção 6 do CLAUDE.md é explícita: a definição de "viral" é PLUGÁVEL (limiar
de views ou top percentil por categoria/janela), e o cuidado principal é viés
de seleção — rotular um vídeo como "não viral" só porque ele ainda não teve
tempo de decolar contamina o dataset. As duas estratégias abaixo cobrem os
dois casos citados; ambas devolvem o rótulo, nunca decidem POR SI quais
trajetórias comparar (isso é escolha do caller, tipicamente já filtrado por
categoria/janela antes de chegar aqui).
"""
from __future__ import annotations

import numpy as np

from ..engine_a.metrics import crossing_hours
from ..types import Trajectory


def label_by_threshold(
    trajectory: Trajectory, *, threshold: int, min_observed_hours: float
) -> bool | None:
    """Rótulo por limiar absoluto de views, com defesa contra viés de seleção.

    Um vídeo que já cruzou `threshold` é `True`, não importa a idade — o
    rótulo positivo já está provado. Um vídeo que NUNCA cruzou mas ainda não
    foi observado por `min_observed_hours` devolve `None`: ele não teve tempo
    de decolar ainda, então "não viral" seria uma afirmação enganosa, não um
    fato — descarte essas amostras do treino (`label is not None`) em vez de
    tratá-las como negativas. Só depois de `min_observed_hours` sem cruzar o
    limiar é que o rótulo `False` é honesto.
    """
    if crossing_hours(trajectory, threshold) is not None:
        return True
    observed = float(trajectory.t_hours[-1]) if trajectory.t_hours.size else 0.0
    if observed < min_observed_hours:
        return None
    return False


def label_by_percentile(
    trajectories: list[Trajectory], *, top_percent: float
) -> dict[str, bool]:
    """Rótulo relativo: vídeo está no `top_percent`% por views finais DENTRO
    do grupo passado. Não agrupa por categoria/janela sozinho — isso é
    responsabilidade do caller (comparar audiências de escalas muito
    diferentes na mesma leva engana o modelo, então filtre antes de chamar).

    `top_percent=10` marca como viral o decil de maior audiência do grupo.
    Grupos vazios devolvem `{}`; com um único vídeo, ele sempre marca `True`
    (é o próprio topo do grupo, por definição).
    """
    if not trajectories:
        return {}
    finals = {t.video_id: (float(t.views[-1]) if t.views.size else 0.0) for t in trajectories}
    cutoff_value = np.percentile(list(finals.values()), 100 - top_percent)
    return {vid: v >= cutoff_value for vid, v in finals.items()}
