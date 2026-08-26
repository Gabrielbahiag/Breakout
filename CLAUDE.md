# CLAUDE.md — Breakout

> Contexto-mestre do projeto para o Claude Code. **Leia este arquivo inteiro
> antes de gerar ou alterar qualquer código.** Ele unifica o plano do produto, a
> arquitetura de testes e a arquitetura de execução. Documentos de aprofundamento:
> `TESTING.md` (camada de testes) e `ARCHITECTURE.md` (execução/deploy).

---

## 1. O que é o Breakout

Um detector de viralização de vídeos curtos (YouTube Shorts) que cruza
**Algoritmos** e **Ciência de Dados**. Uma base de dados alimenta dois motores
complementares, e um dashboard junta os dois:

- **Motor A (algoritmo):** detecta cedo a "decolagem" de um vídeo na curva de
  crescimento de views — responde *quando* ele começa a viralizar. É detecção
  online de ponto de mudança / rajada em série temporal de streaming.
- **Motor B (dados/IA):** analisa os elementos do vídeo (título, thumbnail,
  duração, engajamento) e explica quais se correlacionam com viralizar — responde
  *o quê / por quê*, com importância de features / SHAP.

**Honestidade epistêmica é feature, não fraqueza.** O Motor A detecta o *quando*
com antecedência mensurável (lead time). O Motor B acha *correlatos*, não causa —
viral é em parte efeito de rede e aleatoriedade. Isso vai explícito no README e nas
métricas. Nunca prometer "a fórmula do viral"; sempre reportar a acurácia real e o
teto honesto do problema.

---

## 2. Estado atual (o que já existe)

O esqueleto **já está construído e roda verde**: `pytest` → 113 testes passando,
**zero `xfail`**. **Fase 0 fechada de verdade**: repo público
(`Gabrielbahiag/Breakout`), Turso em produção, YouTube API key configurada,
coletor rodando no cron do GitHub Actions e já validado com dados reais
(`discover` semeou vídeos, `collect` gravou snapshots reais no Turso). **Motor A
completo** (baseline + CUSUM + Kleinberg + BOCPD + PELT + bake-off com curva de
sensibilidade). **Motor B — Fase 4 fechada** (label + features + model + explain,
validados com dataset sintético de sinal plantado). **Dashboard (`dashboard.py`)
pronto e testado localmente** (modo dados reais + modo demo sintético) — falta só
o deploy no Streamlit Community Cloud (Seção 10). O que está pronto vs. pendente:

**Pronto e testado:** contratos (Protocols), tipos do domínio, gerador de
trajetórias sintéticas (`synth`), fakes de teste, coletor de snapshots, harness de
replay, métricas de lead time (`metrics.py`) e bake-off com curva de
sensibilidade (`benchmark.py`), os detectores do Motor A — `BaselineDetector`
(aceleração), `CusumDetector` (Page-Hinkley, Fase 2), `KleinbergBurstDetector`
(autômato de estados via Viterbi incremental, Fase 3), `BocpdDetector`
(Bayesian Online Change Point Detection, Fase 3 evolução — só confiável em
regime-troca tipo `SLEEPER`, não em rampa contínua) — mais o PELT offline
(`offline.py::segment`, via `ruptures`, para segmentação retroativa). Motor B —
`label.py` (limiar + percentil, defesa contra viés de seleção), `features.py`
(estáticas + engajamento inicial via `snapshots_before`), `model.py`
(RandomForest, métricas honestas), `explain.py` (SHAP TreeExplainer). Janela
anti-vazamento (`window_before`/`snapshots_before`), storage SQL atrás do
contrato (`SqlTrajectoryRepository` — inclui `get_snapshots()` pro Motor B —
com **Turso como banco atual em produção** e SQLite local como fallback/dev),
política de cadência (`policy`), composition root, CLI (Typer), settings,
adaptador real da YouTube API (filtrado por `videoDuration=short`, thumbnail
incluída de graça no `fetch_metadata`), e os três workflows do GitHub Actions
(`ci`, `collect` em cron, `discover` de disparo manual — este último existe
porque `libsql-experimental` não tem wheel para Windows, então nada que
precise de `[prod]` roda na máquina de trabalho). Motor B multimodal (Fase 5)
— `thumbnail.py` (CV: brilho/saturação/colorfulness/densidade de bordas via
OpenCV, contagem de rosto descartada porque o `opencv-python` 5.x removeu o
`CascadeClassifier`) e `transcript.py` (heurísticas de texto sobre a legenda
do YouTube, buscada em `collect/transcript_api.py` — decisão explícita de usar
legenda em vez de Whisper, evita baixar áudio/vídeo e rodar modelo pesado).
Ambas OPCIONAIS via `features.py`'s `with_multimodal=False` por padrão
(thumbnail baixa imagem pela rede a cada chamada; ligar por padrão tornaria
`extract_features` lenta/dependente de rede sem o caller pedir).

**Pendente:** treinar/explicar o modelo sobre dados REAIS (falta acumular
outcomes, agora incluindo as features multimodais), e o deploy do dashboard no
Streamlit Community Cloud (o código já está pronto).

---

## 3. Bootstrap do zero

Você tem Python instalado. **O banco ATUAL do projeto é o Turso** (SQLite na
nuvem) — é ele que o `initdb`/`collect`/`detect` usam. O SQLite local continua
como fallback automático (quando `TURSO_*` está vazio) e é o que a suíte de testes
usa por baixo, então **os testes rodam offline, sem Turso e sem rede**.

**Passo A — ambiente + testes (offline, não precisa de Turso):**
```bash
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -e ".[dev]"           # núcleo + testes (ruptures/PELT já incluído)
pytest -q                         # tudo verde, sem tocar rede
```
**Na máquina de trabalho (Windows sem admin), pare por aqui.** `[prod]`
(`libsql-experimental`) não tem wheel pra Windows e não builda sem toolchain
Rust+MSVC — tentar instalar só desperdiça tempo. Tudo que precisa de `[prod]`
(`initdb`/`discover`/`collect` contra o Turso de verdade) roda no GitHub
Actions, nunca localmente — ver Passo B. Em Mac/Linux, `pip install -e
".[dev,prod]"` funciona normal e os comandos abaixo podem rodar direto.

**Passo B — configurar o Turso (o banco atual):**

O CLI do Turso também não tem binário pra Windows (só Darwin/Linux nos
releases oficiais). Caminho que funciona em qualquer SO: o dashboard web.
1. Crie conta em `app.turso.tech` (login GitHub é o mais rápido).
2. Crie um banco (ex: `breakout`) — a página do banco mostra a **URL de
   conexão** (`libsql://...`) → isso é o `TURSO_DATABASE_URL`.
3. Gere um token na mesma página → isso é o `TURSO_AUTH_TOKEN`.
4. Copie `.env.example` para `.env` e preencha os dois (e `YOUTUBE_API_KEY`).
5. Adicione os mesmos três valores como **Secrets do GitHub Actions**
   (Settings → Secrets and variables → Actions) — é de lá que `collect.yml` e
   `discover.yml` os leem.

Não existe `initdb` separado pra rodar: o comando `collect` já chama
`repo.init_schema()` sozinho (idempotente) na primeira execução — então o
primeiro `collect --once` no GitHub Actions já aplica o schema no Turso.

Pra semear a carteira de vídeos, dispare o workflow `discover` manualmente
(aba Actions do GitHub → discover → Run workflow, com uma query de busca) —
ele roda em `ubuntu-latest`, onde `[prod]` instala normal.

A partir daqui dá para desenvolver os motores inteiros usando o gerador sintético
como fonte de verdade-conhecida — não precisa esperar a coleta real acumular
pra iterar nos detectores.

> Notas: (1) a conexão com o Turso é **remota pura por HTTP** (`connection.py`) —
> correta para os runners efêmeros; o SDK Python do Turso está em transição, então
> confira a assinatura de `connect()` em docs.turso.tech/sdk/python se algo
> quebrar. (2) Se o proxy corporativo bloquear o PyPI, aponte o pip para o espelho
> interno. (3) Deixe `TURSO_*` vazio no `.env` para trabalhar 100% offline no
> SQLite local quando quiser — é assim que a suíte de testes já roda.

---

## 4. Princípios inegociáveis (guardrails)

Estes princípios têm precedência sobre conveniência. Não os viole ao gerar código.

1. **Núcleo append-only sagrado.** Os `snapshots` são a verdade insubstituível — a
   API só dá contagem pontual, a trajetória histórica não existe em endpoint
   nenhum, então cada snapshot perdido é um buraco permanente. Tudo o mais
   (trajetórias, features, detecções, rótulos, modelo) é **derivado** e
   recomputável a partir dos snapshots.
2. **O coletor JAMAIS roda código de modelo.** Ele faz uma coisa só: pega stats e
   persiste. Um bug no detector nunca pode ter a chance de derrubar a coleta.
   Detecção é sempre um passo separado, sobre dados já guardados.
3. **Fake > mock.** Preferir fakes (implementações reais em memória) a mocks
   (stubs que afirmam chamadas). Mockar SÓ a fronteira externa real: a rede, via o
   adaptador fino `YouTubeClient` — nunca o `google-api-python-client` cru.
4. **Test-first.** Todo comportamento novo nasce de um teste. Código científico se
   testa por propriedades (`Hypothesis`) e verdade-conhecida sintética, nunca por
   `assert score == 0.73`.
5. **Contratos são as fronteiras.** Coleta, storage, motores e dashboard conversam
   pelos Protocols (Seção 7), não por implementações concretas.
6. **Anti-vazamento (data leakage).** Toda feature do Motor B só pode enxergar
   pontos ATÉ o instante de rotulagem, sempre via `engine_b/windows.py`
   (`window_before` para `Trajectory`, `snapshots_before` para o histórico bruto
   com likes/comments — mesma barreira, duas formas de dado). Há um teste-guarda
   que trava isso (`test_no_leakage.py`, e `test_features.py` testa o USO real).
7. **Cota: descobrir é caro, amostrar é barato.** `search.list` = 100 unidades
   (~100 buscas/dia); `videos.list` = 1 unidade por lote de 50 IDs. Ser parcimonioso
   na descoberta, generoso na amostragem.
8. **Cadência irregular é tolerada por design.** Trajetórias usam timestamps reais;
   nunca assumir intervalos perfeitos entre snapshots.

---

## 5. Arquitetura — visão

**Restrição que molda tudo:** o projeto é desenvolvido numa máquina de trabalho
**sem admin**, que não fica ligada 24/7. Logo a coleta contínua **não pode viver
nessa máquina** — ela é terceirizada para a nuvem (grátis). Desenvolvimento na
máquina; execução na nuvem.

```
  GitHub Actions (CI)          GitHub Actions (cron :23)        Streamlit Cloud
  pytest a cada push     ┌───► breakout collect --once          dashboard (replay
  → selo verde           │     (best-effort; tolera atraso)     ao vivo do Motor A)
                         │            │ escreve                       │ lê
                         │      ┌─────▼───────────────────────┐       │
                         └──────│  TURSO (libSQL / SQLite)     │◄──────┘
                                │  verdade: videos, snapshots  │
                                │  derivado: detections, labels│
                                └─────────────────────────────┘
```

Três ciclos de vida sobre um núcleo e um storage: **coletor** (efêmero, só escreve
a verdade), **jobs offline** de análise (batch, só escrevem derivado) e
**dashboard** (read-only). Em dev, o Turso é substituído por um SQLite local — a
troca é só a conexão no composition root.

---

## 6. Os dois motores

**Motor A — detecção de decolagem.** Reformulação formal: detecção online de ponto
de mudança / rajada em série de streaming, com o trade-off central **detectar cedo
× não dar alarme falso**. Implementado em camadas:
1. Baseline — velocidade/aceleração (EWMA). ✅ pronto (`baseline.py`).
2. CUSUM / Page-Hinkley. ✅ pronto (`changepoint.py::CusumDetector`, Fase 2).
3. Burst detection de Kleinberg (o algoritmo canônico de rajada). ✅ pronto
   (`changepoint.py::KleinbergBurstDetector`, adaptação online via Viterbi
   incremental, Fase 3).
4. BOCPD (probabilístico, entrega incerteza). ✅ pronto
   (`changepoint.py::BocpdDetector`). Estruturalmente diferente dos outros
   três: detecta MUDANÇA DE REGIME (não aceleração), então só é confiável em
   arquétipos com um "antes" calmo pra comparar (`SLEEPER` — e dispara ANTES
   até da inflexão nominal). Cego pro `ROCKET`/`SLOW_BURN` (rampa contínua,
   sem quebra discreta) — limitação honesta do método, não bug; ver o
   docstring da classe para os dois problemas empíricos encontrados e
   corrigidos (viés de partida fria; simetria alta/baixa do teste de reset).
5. PELT (offline, para segmentar curvas históricas). ✅ pronto
   (`offline.py::segment`, via `ruptures`). Não é um `Detector` (Protocol
   online) — vê a trajetória inteira de uma vez. Serve pra anotar
   retroativamente onde a decolagem aconteceu em curvas já coletadas
   (sintéticas ou REAIS), não pra alarme em tempo real.

Métrica central (o pulo do gato): **lead time** — quantas horas antes de o vídeo
cruzar o limiar de "viral" o detector disparou. Sobre isso se constrói a curva
earliness × acurácia e precisão/recall dos alarmes (Fase 2, `benchmark.py`).

**Motor B — análise dos elementos.** Features: metadados (título, duração, tags,
horário, tamanho do canal), engajamento inicial (velocidade de likes/comentários),
e multimodal (Fase 5, opcional via `with_multimodal=True`) — thumbnail via CV
(`thumbnail.py`) e legenda do YouTube (`transcript.py`, não Whisper — ver Seção
12). Modelo classifica viral vs não-viral e explica com SHAP. **Definição de
"viral" (rótulo)**
é plugável (limiar de views ou top percentil por categoria/janela). **Cuidado com
viés de seleção:** amostrar vídeos cedo (perto do upload) e variados, senão o
rótulo engana o modelo.

Como se conectam: o Motor A dispara "este vídeo está decolando agora" (*quando*); o
Motor B responde "e estes elementos se associam ao estouro" (*o quê*). O dashboard
une a curva com o ponto de decolagem sinalizado + os fatores associados,
compartilhando a mesma base e a mesma definição de rótulo.

---

## 7. Contratos (`src/breakout/contracts.py`)

Quatro Protocols. Cada um é alvo de fake nos testes E contrato da implementação
real. Structural typing (`typing.Protocol`) — não exige herança.

- **`Clock`** — `now() -> datetime`. Tempo é dependência injetada; nunca
  `datetime.now()` solto no coletor. Real: `SystemClock`. Teste: `ManualClock`.
- **`YouTubeClient`** — `search_recent / fetch_stats / fetch_metadata`. Adaptador
  fino sobre a API. Real: `YouTubeApiClient`. Teste: `FakeYouTubeClient`.
- **`TrajectoryRepository`** — `save_snapshot / save_metadata / get_trajectory /
  video_ids`. Real: `SqlTrajectoryRepository` (SQLite local ou Turso). Teste:
  `InMemoryTrajectoryRepository`. Ambos passam os mesmos testes de contrato.
- **`Detector`** — `update(t_hours, views) -> Detection | None` + `reset()`.
  Contrato online do Motor A. baseline/CUSUM/Kleinberg/BOCPD são implementações
  intercambiáveis — é o que permite o bake-off de detectores.

---

## 8. Mapa do código

```
breakout/
├── CLAUDE.md            # este arquivo (contexto-mestre)
├── TESTING.md           # aprofundamento da camada de testes
├── ARCHITECTURE.md      # aprofundamento da execução/deploy
├── planning/            # Fase 7: planos detalhados ainda não implementados
├── pyproject.toml       # deps, extras [dev]/[prod]/[dashboard]/[engines], config do pytest
├── .env.example         # YOUTUBE_API_KEY, TURSO_* (copie para .env em dev)
├── .github/workflows/
│   ├── ci.yml           # roda pytest a cada push
│   ├── collect.yml      # coletor agendado (cron), chama `collect --once`
│   └── discover.yml     # semeia a carteira (disparo manual — gasta cota de search)
├── src/breakout/
│   ├── types.py         # Snapshot, VideoMetadata, Trajectory, Detection, GroundTruth, Archetype
│   ├── contracts.py     # os 4 Protocols
│   ├── settings.py      # config via pydantic-settings
│   ├── clock.py         # SystemClock (real)
│   ├── composition.py   # composition root: contratos ↔ impl reais
│   ├── cli.py           # Typer: initdb/discover/collect/detect/dashboard
│   ├── __main__.py      # `python -m breakout`
│   ├── collect/
│   │   ├── snapshots.py     # SnapshotCollector (usa Clock+Client+Repo injetados)
│   │   ├── policy.py        # cadência adaptativa sem estado (select_due/retire_stale)
│   │   ├── youtube_api.py   # adaptador real (403 quota vs 429 rate limit)
│   │   └── transcript_api.py# ✅ Fase 5: legenda via youtube-transcript-api (não é a Data API)
│   ├── storage/
│   │   ├── schema.sql       # verdade (videos, snapshots) vs derivado (detections, labels)
│   │   ├── sql_repository.py# SqlTrajectoryRepository (sqlite local OU Turso)
│   │   └── connection.py     # fábrica: Turso se configurado, senão SQLite WAL
│   ├── engine_a/
│   │   ├── baseline.py      # ✅ detector por aceleração (Camada 1)
│   │   ├── changepoint.py   # ✅ CusumDetector / KleinbergBurstDetector / BocpdDetector
│   │   ├── offline.py       # ✅ PELT (segmentação offline via `ruptures`)
│   │   ├── replay.py        # run_detector: replay online (é teste E "modo simulação")
│   │   ├── metrics.py       # lead_time_hours, crossing_hours
│   │   └── benchmark.py     # ✅ bake-off: precisão/recall, earliness, sensitivity_curve
│   ├── engine_b/
│   │   ├── windows.py       # window_before / snapshots_before: barreira anti-vazamento
│   │   ├── label.py         # ✅ label_by_threshold / label_by_percentile (viés de seleção)
│   │   ├── features.py      # ✅ extract_features: estáticas (upload) + dinâmicas (via snapshots_before)
│   │   ├── model.py         # ✅ RandomForestClassifier (train/evaluate, métricas honestas)
│   │   ├── explain.py       # ✅ SHAP (TreeExplainer): feature_importance, shap_values
│   │   ├── thumbnail.py     # ✅ Fase 5: features de CV (brilho/saturação/colorfulness/bordas)
│   │   └── transcript.py    # ✅ Fase 5: features de texto sobre a legenda
│   ├── synth/
│   │   └── trajectories.py  # gerador sintético com verdade-conhecida (5 arquétipos)
│   └── dashboard.py     # ✅ Streamlit: modo "dados reais" (Turso) + "demo sintético"
└── tests/
    ├── conftest.py          # fixtures (fakes, rng com seed, fábrica de trajetórias)
    ├── fakes/               # ManualClock, InMemoryTrajectoryRepository, FakeYouTubeClient
    ├── unit/                # synth, metrics, baseline, repository, sql_repository, policy, no_leakage, changepoint
    └── integration/         # pipeline offline ponta a ponta (fake API→coletor→repo→detector)
```

---

## 9. Camada de testes (resumo — detalhe em TESTING.md)

Duas naturezas, duas filosofias. **Engenharia** (coletor, storage, API): mock da
fronteira, determinístico, `assert x == y`. **Ciência** (detectores, modelo):
propriedades (`Hypothesis`), contratos e verdade-conhecida sintética.

**A peça-chave é o gerador sintético** (`synth/trajectories.py`): curvas de
views-no-tempo com decolagem *rotulada* e teto *conhecido*. Dá lead time exato,
roda todos os detectores nas mesmas curvas (bake-off), e desbloqueia o Motor A
inteiro na Fase 0 sem esperar a coleta acumular. O mesmo truque valida o Motor B
(plantar sinal conhecido → o modelo o encontra?). Os cinco arquétipos:

| Arquétipo      | Fenômeno                      | Estressa                     |
|----------------|-------------------------------|------------------------------|
| `ROCKET`       | decola quase no upload        | subida abrupta               |
| `SLOW_BURN`    | sobe devagar, estoura tarde   | sinal fraco por muito tempo  |
| `SLEEPER`      | morto por dias, depois acorda | change point tardio          |
| `FLASH_IN_PAN` | sobe rápido e murcha          | **resistência a alarme falso** |
| `STILLBORN`    | nunca sai do chão             | a taxa-base / controle       |

Marcadores: `unit`, `integration`, `network` (desligado por padrão), `slow`,
`benchmark`. `pytest` roda tudo menos rede. Sempre usar seed fixa em geradores
aleatórios (reprodutibilidade); floats com `pytest.approx` / `assert_allclose`,
nunca `==`.

---

## 10. Indo pro ar (o que resta depois do Turso)

Itens 1-4 já estão feitos (Fase 0 fechada — Seção 12). O que resta pro deploy
completo:

1. ✅ **Chave da YouTube API** (Google Cloud Console).
2. ✅ **Repositório público no GitHub** (`Gabrielbahiag/Breakout`) — CI verde.
3. ✅ **Secrets** (`YOUTUBE_API_KEY`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`)
   nos Secrets do GitHub Actions. **Nunca no disco da máquina do trabalho.**
4. ✅ **Coletor ligado** (`collect.yml`, cron `:23`) — já acumulando trajetórias
   reais.
5. ⬜ **Dashboard no Streamlit Community Cloud**: `dashboard.py` já existe e
   funciona (testado localmente com `AppTest`) — falta só o deploy em si.
   Passos: criar conta em `share.streamlit.io` (login GitHub), apontar pro
   repo/`src/breakout/dashboard.py`, e configurar os MESMOS três secrets nos
   **Secrets do app Streamlit** (formato TOML, painel do app → Settings →
   Secrets). O ambiente do Streamlit Cloud é Linux, então `[prod]` (libsql)
   instala normal — diferente da máquina de trabalho. Dependências pra
   declarar no deploy: `.[prod,dashboard]`.

> Perf com Turso remoto: `save_snapshot` faz `commit()` por chamada, o que é um
> round-trip HTTP por snapshot. Numa coleta em lote isso é lento — otimização de
> follow-up: comitar UMA vez por rodada de coleta (não por snapshot). Rastreado
> como melhoria; não bloqueia o MVP.

Gotchas do deploy: o cron do GitHub Actions é **best-effort** (atrasos de 5-30min
normais; usar minuto fora do pico, ex. :23) e **workflows em repo público são
desativados após 60 dias sem atividade** (mitigar com commits/keepalive; sempre ter
`workflow_dispatch`). O Streamlit grátis **dorme após 12h** e tem **~1GB de RAM** —
o dashboard puxa UMA trajetória por vez, nunca o banco inteiro na memória.

---

## 11. Stack

**Núcleo:** `python` · `numpy` · `pandas` · `typer` · `pydantic-settings` ·
`ruptures` (PELT, Motor A) · `scikit-learn` (`model.py`) · `shap` (`explain.py`) ·
`opencv-python` (`thumbnail.py`, Fase 5) · `httpx` (download da thumbnail).
`scipy` é dependência direta (Student-t/logsumexp do BOCPD), embora só apareça
explícita transitivamente via `ruptures`.
**Testes (`[dev]`):** `pytest` · `pytest-cov` · `hypothesis` · `time-machine` ·
`respx` · `syrupy`.
**Produção (`[prod]`):** `google-api-python-client` · `libsql-experimental` (Turso).
**NÃO instala no Windows sem admin** (`libsql-experimental` não tem wheel pra
Windows nem builda sem toolchain Rust+MSVC). `youtube-transcript-api` (Fase 5,
legenda) mora aqui também — só usado por `discover`, nunca testado direto (mesmo
motivo de `google-api-python-client` ficar em `[prod]`, não em core). Na máquina
de trabalho, instale só `.[dev]`; tudo que precisa de `[prod]` roda via GitHub
Actions (`collect`/`discover`), nunca localmente.
**Dashboard (`[dashboard]`):** `streamlit` (Altair vem embutido — não precisa
listar). `dashboard.py` roda local contra SQLite (testável na máquina de
trabalho, sem `[prod]`) e em produção contra o Turso (Streamlit Cloud, Linux,
onde `[prod]` instala normal — precisa de `.[prod,dashboard]` no deploy).
**Motores (`[engines]`, fases seguintes):** `river` (online, ainda não usado
por nada) · `matplotlib`/`plotly`.
**Dev sem admin:** `venv` ou `uv`; Docker está fora (e não é necessário).

---

## 12. Roadmap por fases

- **Fase 0 — Fundação + coleta.** ✅ repo/pyproject/pytest, coletor, storage,
  `discover` real, chave da API, coleta ligada no cron do GitHub Actions e
  validada com dados reais (fechada em 2026-08-21).
- **Fase 1 — Trajetórias + baseline (Motor A).** ✅ baseline por aceleração + synth.
  Dataset de curvas a partir da coleta real: o mecanismo já existe
  (`get_trajectory` monta a curva de qualquer vídeo com ≥1 snapshot) — falta só
  tempo de cron acumulando múltiplos snapshots por vídeo, não código.
- **Fase 2 — Detecção online + métricas (Motor A).** ✅ `CusumDetector`
  (Page-Hinkley, xfail removido). ✅ `benchmark.py` (bake-off: precisão/recall de
  alarme sobre `takeoff_hours`, earliness via `lead_time_hours`, mesma bateria
  p/ todos os detectores). ⬜ curva earliness×acurácia (variar sensibilidade de
  cada detector e plotar o trade-off) fica para quando o dashboard existir.
- **Fase 3 — Algoritmos avançados (Motor A).** ✅ Kleinberg. ✅ BOCPD (com a
  limitação honesta de só disparar em regime-troca, não em rampa contínua).
  ✅ PELT offline (`ruptures`). ✅ curva earliness×acurácia (`sensitivity_curve`
  em `benchmark.py`). Motor A fechado — só falta BOCPD/PELT rodarem sobre
  dados REAIS quando a Fase 1 acumular trajetórias longas o suficiente.
- **Fase 4 — Elementos: metadados (Motor B).** ✅ Fechada. `label.py` (limiar +
  percentil, com defesa contra viés de seleção). `features.py` (estáticas +
  engajamento inicial via `snapshots_before`; exigiu estender o contrato
  `TrajectoryRepository` com `get_snapshots()`, já que `get_trajectory` só
  carrega views). `model.py` (RandomForest, métricas honestas — nunca só
  accuracy, classe viral é minoritária). `explain.py` (SHAP TreeExplainer).
  Validado test-first com dataset sintético de sinal PLANTADO (mesmo truque
  do Motor A) — falta treinar/explicar sobre dados REAIS quando a coleta
  acumular outcomes suficientes.
- **Fase 5 — Elementos: multimodal (Motor B).** ✅ Fechada. `thumbnail.py`
  (features de CV: brilho, saturação, colorfulness, densidade de bordas —
  sem contagem de rosto, o `opencv-python` 5.x removeu o `CascadeClassifier`
  clássico e o substituto exige baixar um modelo ONNX à parte, o que
  contradiz a decisão abaixo). `transcript.py` + `collect/transcript_api.py`
  (`youtube-transcript-api`): decisão consciente de usar LEGENDA do YouTube
  em vez de Whisper — Whisper exigiria baixar áudio/vídeo (yt-dlp/ffmpeg) e
  rodar um modelo pesado (torch), lento e frágil demais pro GitHub Actions
  free tier; legenda é best-effort, sem mídia, sem gastar cota da Data API.
  Ambas opcionais em `features.py` (`with_multimodal=False` por padrão).
- **Fase 6 — Unificação + dashboard.** ✅ `dashboard.py` (Streamlit): curva com
  ponto de decolagem marcado, KPIs de lead time, e a seção do Motor B (SHAP
  sobre demo sintético enquanto dado real não acumula outcomes; features reais
  quando há metadados). Testado localmente com `AppTest` (sem navegador) nos
  dois modos. ⬜ deploy no Streamlit Community Cloud (conta + conectar o repo —
  ver Seção 10) e README com o demo.
- **Fase 7 — Melhorias planejadas (2026-08-25, ainda não implementadas).**
  Planejamento detalhado em `planning/` (test-first — cada arquivo lista os
  testes a escrever ANTES do código):
  - ⬜ **Reconhecimento facial na thumbnail** via `cv2.FaceDetectorYN` (rede
    YuNet) — `planning/reconhecimento-facial.md`. Reverte a decisão da Fase
    5 de descartar contagem de rosto: o modelo `.onnx` é pequeno (~1-2MB,
    não comparável a Whisper), plano é empacotá-lo como package data
    (mesmo padrão do `schema.sql`).
  - ⬜ **Transcrição via Whisper como FALLBACK** (só quando não há legenda)
    — `planning/transcricao-whisper.md`. `faster-whisper` (não
    `openai-whisper`, evita dependência de `torch`); pipeline baixa só
    áudio via `yt-dlp`, nunca persiste mídia. Novo extra `[whisper]`,
    op-in por execução do `discover.yml` (custo de tempo por vídeo ainda
    não medido).
  - ⬜ **Automação do `discover`** (multi-nicho + idioma) —
    `planning/discover-automatico.md`. Config versionada
    `discover_topics.yml` (lista de nichos escolhidos pelo usuário, não um
    termo fixo); `search_recent` ganha parâmetro `language`
    (`relevanceLanguage` da API); `discover.yml` ganha `schedule:` além do
    `workflow_dispatch` existente.
  - ⬜ **Dashboard: multimodal + disparo de coleta** —
    `planning/dashboard-multimodal-e-coleta.md`. Parte 1: mostrar
    thumbnail/transcrição no dashboard (`with_multimodal=True` opcional,
    igual ao `features.py`). Parte 2 (confirmada pelo usuário): botão no
    dashboard dispara `collect`/`discover` via API do GitHub
    (`workflow_dispatch` remoto) — preserva "dashboard read-only" (nunca
    escreve no Turso direto), mas introduz o PRIMEIRO secret do projeto com
    poder de escrita de verdade (GitHub PAT fine-grained, escopo Actions).

---

## 13. Definição de "MVP pronto"

Um coletor acumulando trajetórias de views; o **Motor A** sinaliza a decolagem com
**lead time mensurável** sobre o momento em que o vídeo de fato viraliza; o **Motor
B** classifica viral vs não-viral e mostra via SHAP **quais elementos se
correlacionam**; e um dashboard junta a curva (com o ponto de decolagem) e os
fatores — tudo com as métricas reais e honestas no README.

---

## 14. Regras de trabalho para o agente

- **Sempre rodar `pytest -q` antes de considerar qualquer tarefa pronta.** Verde é
  a definição de pronto; quando implementar um detector avançado, o `xfail`
  correspondente deve virar `xpass`, então remova o marcador `xfail`.
- **Nunca colocar código de modelo/detecção dentro do coletor** (Princípio 2).
- **Toda feature do Motor B passa por `window_before`** (Princípio 6). Se precisar
  de dado do futuro, você está errado.
- **Adicionar/atualizar teste junto com código.** Novo detector → testes de
  propriedade contra os arquétipos sintéticos, no mínimo: nunca dispara em t=0,
  dispara nos arquétipos que decolam, silencia no `STILLBORN`.
- **Respeitar os contratos.** Nova fonte de dados ou storage = nova implementação
  de Protocol, não vazamento de detalhe concreto para o resto do sistema.
- **Docstrings e comentários em português.** Mensagens de commit descritivas.
- **Nada de secret no código nem no repositório.** Sempre via settings/env.
- **Preferir editar e condensar a duplicar.** Manter o núcleo separado da interface.
