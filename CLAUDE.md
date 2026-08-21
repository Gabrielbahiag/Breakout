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

O esqueleto **já está construído e roda verde**: `pytest` → 69 testes passando,
**zero `xfail`** (o autômato de Kleinberg foi o último a cair). **Fase 0 fechada
de verdade**: repo público (`Gabrielbahiag/Breakout`), Turso em produção,
YouTube API key configurada, coletor rodando no cron do GitHub Actions e já
validado com dados reais (`discover` semeou vídeos, `collect` gravou snapshots
reais no Turso). **Motor A completo até a Fase 3** (baseline + CUSUM + Kleinberg
+ bake-off). O que está pronto vs. pendente:

**Pronto e testado:** contratos (Protocols), tipos do domínio, gerador de
trajetórias sintéticas (`synth`), fakes de teste, coletor de snapshots, harness de
replay, métricas de lead time (`metrics.py`) e bake-off (`benchmark.py`), os três
detectores do Motor A — `BaselineDetector` (aceleração), `CusumDetector`
(Page-Hinkley, Fase 2), `KleinbergBurstDetector` (autômato de estados via Viterbi
incremental, Fase 3) —, janela anti-vazamento, storage SQL atrás do contrato
(`SqlTrajectoryRepository`, com **Turso como banco atual em produção** e SQLite
local como fallback/dev), política de cadência (`policy`), composition root, CLI
(Typer), settings, adaptador real da YouTube API (filtrado por `videoDuration=
short`), e os três workflows do GitHub Actions (`ci`, `collect` em cron,
`discover` de disparo manual — este último existe porque `libsql-experimental`
não tem wheel para Windows, então nada que precise de `[prod]` roda na máquina de
trabalho).

**Pendente:** BOCPD/PELT (evolução do Motor A), curva earliness×acurácia
(evolução do `benchmark.py`), o Motor B inteiro (label, features, model,
explain, multimodal) e o dashboard.

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
pip install -e ".[dev,prod]"      # [dev]=testes, [prod]=cliente Turso + YouTube
pytest -q                         # tudo verde, sem tocar rede
```

**Passo B — configurar o Turso (o banco atual):**
```bash
# instalar a CLI do Turso (uma vez) e logar
curl -sSfL https://get.tur.so/install.sh | bash   # Windows: ver docs.turso.tech
turso auth signup                 # abre o navegador, login via GitHub

# criar o banco e pegar as credenciais
turso db create breakout
turso db show breakout --url      # -> TURSO_DATABASE_URL  (libsql://...)
turso db tokens create breakout   # -> TURSO_AUTH_TOKEN
```
Copie `.env.example` para `.env` e preencha `TURSO_DATABASE_URL` e
`TURSO_AUTH_TOKEN` (e `YOUTUBE_API_KEY` quando for coletar). Então:
```bash
python -m breakout initdb         # aplica o schema NO TURSO
```

A partir daqui dá para desenvolver os motores inteiros usando o gerador sintético
como fonte de verdade-conhecida; a coleta real precisa só da chave da YouTube API.

> Notas: (1) a conexão com o Turso é **remota pura por HTTP** (`connection.py`) —
> correta para os runners efêmeros; o SDK Python do Turso está em transição, então
> confira a assinatura de `connect()` em docs.turso.tech/sdk/python se algo
> quebrar. (2) Se o proxy corporativo bloquear o PyPI, aponte o pip para o espelho
> interno. (3) Deixe `TURSO_*` vazio no `.env` para trabalhar 100% offline no
> SQLite local quando quiser.

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
   pontos ATÉ o instante de rotulagem, sempre via `engine_b/windows.py::window_before`.
   Há um teste-guarda que trava isso.
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
4. BOCPD (probabilístico, entrega incerteza). ⬜ evolução.
5. PELT (offline, para segmentar curvas históricas). ⬜ evolução.

Métrica central (o pulo do gato): **lead time** — quantas horas antes de o vídeo
cruzar o limiar de "viral" o detector disparou. Sobre isso se constrói a curva
earliness × acurácia e precisão/recall dos alarmes (Fase 2, `benchmark.py`).

**Motor B — análise dos elementos.** Features: metadados (título, duração, tags,
horário, tamanho do canal), engajamento inicial (velocidade de likes/comentários),
e multimodal como evolução (thumbnail via CV, transcrição via NLP). Modelo
classifica viral vs não-viral e explica com SHAP. **Definição de "viral" (rótulo)**
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
├── pyproject.toml       # deps, extras [dev]/[prod]/[engines], config do pytest
├── .env.example         # YOUTUBE_API_KEY, TURSO_* (copie para .env em dev)
├── .github/workflows/
│   ├── ci.yml           # roda pytest a cada push
│   └── collect.yml      # coletor agendado (cron), chama `collect --once`
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
│   │   └── youtube_api.py   # adaptador real (403 quota vs 429 rate limit)
│   ├── storage/
│   │   ├── schema.sql       # verdade (videos, snapshots) vs derivado (detections, labels)
│   │   ├── sql_repository.py# SqlTrajectoryRepository (sqlite local OU Turso)
│   │   └── connection.py     # fábrica: Turso se configurado, senão SQLite WAL
│   ├── engine_a/
│   │   ├── baseline.py      # ✅ detector por aceleração (Camada 1)
│   │   ├── changepoint.py   # ⬜ CusumDetector / KleinbergBurstDetector (stubs xfail)
│   │   ├── replay.py        # run_detector: replay online (é teste E "modo simulação")
│   │   └── metrics.py       # lead_time_hours, crossing_hours
│   ├── engine_b/
│   │   └── windows.py       # window_before: barreira anti-vazamento
│   └── synth/
│       └── trajectories.py  # gerador sintético com verdade-conhecida (5 arquétipos)
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

O Turso (banco atual) já foi configurado no bootstrap (Seção 3). O que resta para
o deploy completo:

1. **Chave da YouTube API** (Google Cloud Console) → habilita a coleta real.
2. **Repositório público no GitHub** → CI (`ci.yml`) roda o pytest, selo verde.
3. **Secrets** → `YOUTUBE_API_KEY`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` nos
   **Secrets do GitHub Actions** (e do Streamlit). **Nunca no disco da máquina do
   trabalho.**
4. **Ligar o coletor** (`collect.yml`) → começa a acumular trajetórias. Fazer isto
   CEDO: dados levam tempo, é a decisão mais importante do projeto.
5. **Dashboard no Streamlit Community Cloud** → deploya do GitHub, lê o Turso,
   roda o Motor A como replay ao vivo.

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

**Núcleo:** `python` · `numpy` · `pandas` · `typer` · `pydantic-settings`.
**Testes (`[dev]`):** `pytest` · `pytest-cov` · `hypothesis` · `time-machine` ·
`respx` · `syrupy`.
**Produção (`[prod]`):** `google-api-python-client` · `libsql-experimental` (Turso).
Como o Turso é o banco atual, instale `.[dev,prod]` já no dev (o cliente libsql é
necessário para falar com o banco; os testes continuam offline via SQLite).
**Motores (`[engines]`, fases seguintes):** `ruptures` (PELT) · `river` (online) ·
`scikit-learn` · `shap` · `matplotlib`/`plotly` · `streamlit`. Multimodal (evolução):
`opencv`/`Pillow` (thumbnail), `whisper` (transcrição).
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
- **Fase 3 — Algoritmos avançados (Motor A).** ✅ Kleinberg. ⬜ BOCPD; PELT offline.
- **Fase 4 — Elementos: metadados (Motor B).** ⬜ `label.py` (definição de viral +
  amostragem sem viés) · `features.py` · `model.py` · `explain.py` (SHAP).
- **Fase 5 — Elementos: multimodal (Motor B).** ⬜ thumbnail (CV) + transcrição.
- **Fase 6 — Unificação + dashboard.** ⬜ curva + ponto de decolagem + fatores;
  README com o demo (lead time visível) e as métricas honestas.

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
