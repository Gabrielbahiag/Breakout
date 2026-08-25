"""Dashboard do Breakout — Streamlit Community Cloud (Fase 6).

Read-only: nunca escreve no banco (Ciclo de vida da Seção "Ciclos de vida" do
ARCHITECTURE.md). Puxa UMA trajetória por vez, nunca o banco inteiro na
memória — o free tier do Streamlit Cloud tem ~1GB de RAM.

Dois modos:
  - **Demo sintético**: gerador de verdade-conhecida do Motor A. Existe
    porque a coleta real começou há pouco tempo e ainda não tem trajetórias
    longas o suficiente — mostra o pipeline inteiro funcionando, sem esperar
    semanas de dado real acumular.
  - **Dados reais**: lê o Turso (ou SQLite local em dev) via o composition
    root, exatamente como o resto do sistema.

Honestidade epistêmica (Seção 1 do CLAUDE.md): o Motor A reporta lead time
MEDIDO, nunca promete detectar tudo. O Motor B mostra CORRELAÇÃO, nunca
"a fórmula do viral".
"""
from __future__ import annotations

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from sklearn.model_selection import train_test_split

from breakout import composition
from breakout.engine_a.baseline import BaselineDetector
from breakout.engine_a.changepoint import BocpdDetector, CusumDetector, KleinbergBurstDetector
from breakout.engine_a.metrics import crossing_hours, lead_time_hours
from breakout.engine_a.replay import run_detector_all
from breakout.engine_b import explain as explain_mod
from breakout.engine_b import features as features_mod
from breakout.engine_b import model as model_mod
from breakout.synth.trajectories import VIRAL_THRESHOLD_DEFAULT, make_trajectory
from breakout.types import Archetype, Trajectory

st.set_page_config(page_title="Breakout", page_icon=":material/rocket_launch:", layout="wide")

DETECTORS = {
    "baseline (aceleração)": BaselineDetector,
    "cusum (Page-Hinkley)": CusumDetector,
    "kleinberg (rajada)": KleinbergBurstDetector,
    "bocpd (mudança de regime)": BocpdDetector,
}

DETECTOR_DESCRIPTIONS = {
    "baseline (aceleração)": (
        "Olha a velocidade de crescimento das views e dispara quando ela "
        "está acelerando de forma sustentada por várias horas seguidas — o "
        "jeito mais simples de perceber uma decolagem."
    ),
    "cusum (Page-Hinkley)": (
        "Técnica estatística clássica: acumula o quanto a taxa de "
        "crescimento está acima do normal e dispara quando esse acúmulo "
        "foge demais do esperado."
    ),
    "kleinberg (rajada)": (
        "O algoritmo clássico de detecção de 'rajadas'. Modela o vídeo como "
        "estando sempre em um de dois estados — normal ou em rajada — e "
        "decide qual estado explica melhor o que está vendo."
    ),
    "bocpd (mudança de regime)": (
        "Em vez de sim/não, calcula uma PROBABILIDADE de que o vídeo mudou "
        "de regime. Funciona bem pra quem fica quieto e de repente acorda "
        "(SLEEPER) — mas não pra quem já decola rápido desde o início "
        "(ROCKET), porque não tem um 'antes' calmo pra comparar."
    ),
}


# ---- carregamento de dados -------------------------------------------------


@st.cache_resource
def _repo():
    return composition.build().repo


@st.cache_data(ttl="10m")
def _real_video_ids() -> list[str]:
    try:
        return sorted(_repo().video_ids())
    except Exception:
        return []


@st.cache_data(ttl="10m")
def _real_video_titles() -> dict[str, str]:
    """video_id -> título, numa query só (list_metadata) — evita N+1
    round-trips contra o Turso remoto ao popular o seletor do dashboard."""
    try:
        return {m.video_id: m.title for m in _repo().list_metadata() if m.title}
    except Exception:
        return {}


@st.cache_data
def _synthetic_trajectory(archetype: str, seed: int):
    return make_trajectory(Archetype(archetype), seed=seed)


def _load_real_trajectory(video_id: str) -> Trajectory:
    return _repo().get_trajectory(video_id)


@st.cache_data
def _demo_dataset():
    """Dataset sintético do Motor B com um sinal PLANTADO: título com número
    triplica a chance de viralizar, por construção — mesmo truque de
    verdade-conhecida do Motor A, ilustrando o pipeline model.py/explain.py
    enquanto a coleta real não acumula outcomes suficientes."""
    rng = np.random.default_rng(7)
    n = 400
    has_number = rng.integers(0, 2, size=n).astype(float)
    prob = np.where(has_number > 0, 0.45, 0.15)
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


@st.cache_resource
def _demo_model(X_train: pd.DataFrame, y_train: pd.Series):
    return model_mod.train(X_train, y_train)


# ---- página -----------------------------------------------------------


st.title("Breakout")
st.caption("Detector de viralização de vídeos curtos — quando decola (Motor A), e por quê (Motor B).")

with st.sidebar:
    st.subheader("Fonte dos dados")
    mode = st.radio(
        "Modo", ["Demo sintético", "Dados reais"], label_visibility="collapsed"
    )

    if mode == "Demo sintético":
        archetype_name = st.selectbox("Arquétipo", [a.value for a in Archetype])
        seed = st.number_input("Seed", min_value=0, value=1, step=1)
        traj, truth = _synthetic_trajectory(archetype_name, int(seed))
        st.caption(f"Verdade conhecida: decolagem real em t={truth.takeoff_hours}, viral={truth.is_viral}")
        video_id = None
    else:
        ids = _real_video_ids()
        if not ids:
            st.warning(
                "Nenhum vídeo real disponível (banco vazio, ou Turso "
                "inacessível — na máquina de trabalho isso é esperado, ver "
                "Seção 3 do CLAUDE.md)."
            )
            st.stop()
        titles = _real_video_titles()
        video_id = st.selectbox("Vídeo", ids, format_func=lambda vid: titles.get(vid, vid))
        traj = _load_real_trajectory(video_id)

    st.divider()
    st.subheader("Motor A")
    detector_label = st.selectbox("Detector", list(DETECTORS.keys()), index=1)
    st.caption(DETECTOR_DESCRIPTIONS[detector_label])
    threshold = st.number_input(
        "Limiar de viral (views)", min_value=1_000, value=VIRAL_THRESHOLD_DEFAULT, step=10_000
    )

with st.expander("Por que existem 4 detectores, e o que o resultado significa?"):
    bullets = "\n".join(f"- **{k}:** {v}" for k, v in DETECTOR_DESCRIPTIONS.items())
    st.markdown(
        "Os quatro são abordagens matemáticas diferentes pra responder à "
        "MESMA pergunta: **quando esse vídeo começou a decolar?** Rodar os "
        "quatro na mesma curva (o \"bake-off\" do Motor A) mostra que eles "
        "podem discordar — cada um tem pontos fortes e fracos diferentes. "
        "Escolher um aqui simula rodar só ele em produção.\n\n"
        f"{bullets}\n\n"
        "**\"Decolagem detectada em Xh\"** — o detector reprocessa a curva "
        "PONTO A PONTO, como se os dados estivessem chegando ao vivo (sem "
        "ver o futuro). Xh é a primeira hora em que ele ficou confiante de "
        "que o crescimento mudou — não é quando o vídeo viralizou, é quando "
        "o ALGORITMO percebeu o sinal.\n\n"
        "**Lead time** — compara com a linha vermelha do gráfico (quando o "
        "vídeo realmente cruzou o limiar de viral). Detecção ANTES = lead "
        "time positivo (deu tempo de reagir). Detecção DEPOIS = lead time "
        "negativo (o algoritmo chegou atrasado pra esse limiar)."
    )

detector = DETECTORS[detector_label]()
hits = run_detector_all(detector, traj)
first_hit = hits[0] if hits else None
crossing = crossing_hours(traj, int(threshold))
lead = lead_time_hours(first_hit, traj, int(threshold))

with st.container(horizontal=True):
    st.metric("Views (fim da janela observada)", f"{int(traj.views[-1]):,}".replace(",", "."), border=True)
    st.metric(
        "Decolagem detectada",
        f"{first_hit.at_hours:.1f}h" if first_hit is not None else "não detectada",
        border=True,
    )
    st.metric(
        "Cruzou o limiar de viral?",
        f"em {crossing:.1f}h" if crossing is not None else "não (ainda)",
        border=True,
    )
    st.metric(
        "Lead time",
        f"{lead:.1f}h antes" if lead is not None else "—",
        border=True,
    )

df = pd.DataFrame({"t_hours": traj.t_hours, "views": traj.views})
line = (
    alt.Chart(df)
    .mark_line()
    .encode(x=alt.X("t_hours:Q", title="Horas desde a publicação"), y=alt.Y("views:Q", title="Views"))
)
layers = [line]
if first_hit is not None:
    hit_df = pd.DataFrame({"t_hours": [first_hit.at_hours]})
    layers.append(alt.Chart(hit_df).mark_rule(color="orange", strokeDash=[4, 4]).encode(x="t_hours:Q"))
if crossing is not None:
    cross_df = pd.DataFrame({"t_hours": [crossing]})
    layers.append(alt.Chart(cross_df).mark_rule(color="red").encode(x="t_hours:Q"))

with st.container(border=True):
    st.subheader("Curva de crescimento")
    st.altair_chart(alt.layer(*layers))
    st.caption(
        "Linha tracejada laranja = instante em que o detector disparou. "
        "Linha vermelha = instante em que cruzou o limiar de viral."
    )

st.divider()
st.subheader("Motor B — o quê / por quê")
st.caption(
    "Isto explica o MODELO, não o fenômeno — correlação, não causa "
    "(Seção 1 do CLAUDE.md). Viral é em parte efeito de rede e sorte."
)

if mode == "Demo sintético":
    st.info(
        "A coleta real ainda não acumulou outcomes suficientes pra treinar "
        "sobre dados de verdade. Demo abaixo: um sinal PLANTADO (título com "
        "número triplica a chance de viralizar, por construção) — mostra que "
        "o pipeline encontra o sinal que sabemos que existe."
    )
    X_train, X_test, y_train, y_test = _demo_dataset()
    demo_model = _demo_model(X_train, y_train)
    result = model_mod.evaluate(demo_model, X_test, y_test)
    importance = explain_mod.feature_importance(demo_model, X_test)

    with st.container(horizontal=True):
        st.metric("ROC-AUC (teste)", f"{result.roc_auc:.2f}", border=True)
        st.metric("Precisão", f"{result.precision:.2f}", border=True)
        st.metric("Revocação (recall)", f"{result.recall:.2f}", border=True)

    with st.container(border=True):
        st.markdown("**Importância das features (SHAP, |valor médio|)**")
        st.bar_chart(importance, horizontal=True)
else:
    metadata = traj.metadata
    if metadata is None:
        st.info("Este vídeo ainda não tem metadados coletados (rode `discover`).")
    else:
        snapshots = _repo().get_snapshots(video_id)
        max_hours = float(traj.t_hours[-1]) if traj.t_hours.size else 0.0
        if max_hours > 0:
            cutoff = st.slider(
                "Corte de features (horas desde publicação)",
                min_value=0.0,
                max_value=max_hours,
                value=min(24.0, max_hours),
            )
        else:
            cutoff = 0.0
            st.caption("Só 1 snapshot coletado até agora — aguardando mais rodadas do cron.")
        feats = features_mod.extract_features(metadata, snapshots, cutoff_hours=cutoff)
        with st.container(border=True):
            st.markdown("**Features extraídas (visíveis até o corte)**")
            st.dataframe(pd.Series(feats, name="valor").to_frame(), width="stretch")
        st.caption(
            "Ainda sem modelo treinado sobre dados reais (falta acumular "
            "outcomes) — só as features, não uma predição."
        )
