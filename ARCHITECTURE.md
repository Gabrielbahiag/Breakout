# Breakout — Arquitetura de Execução

> Contexto para o Claude Code. Descreve COMO o sistema roda (não como se testa —
> isso está em TESTING.md). Leia antes de mexer em coleta, storage ou deploy.

## A restrição que molda tudo

O projeto é desenvolvido numa máquina de trabalho **sem acesso de administrador**,
que não fica ligada 24/7. Consequência dura: **o coletor não pode viver nessa
máquina** — cada hora desligada é um buraco permanente na curva, e o dado é
insubstituível (a API só dá contagem pontual; a trajetória histórica não existe
em endpoint nenhum). Por isso separamos:

- **Desenvolvimento** → na máquina (sem admin: `uv` ou `python -m venv`, tudo em
  espaço de usuário; Docker está fora e não é necessário).
- **Execução** (coleta contínua) → terceirizada para a nuvem, de graça.

## Topologia: cloud-native, 100% gratuita

```
  GitHub Actions (CI)          GitHub Actions (cron :23)        Streamlit Cloud
  pytest a cada push     ┌───► breakout collect --once          dashboard (replay
  → selo verde           │     (best-effort, tolera atraso)     ao vivo do Motor A)
                         │            │                              │
                         │            ▼ escreve                      │ lê
                         │      ┌─────────────────────────────┐      │
                         └──────│  TURSO (libSQL / SQLite)     │◄─────┘
                                │  verdade: videos, snapshots  │
                                │  derivado: detections, labels│
                                └─────────────────────────────┘
```

- **Coletor** = workflow agendado (`.github/workflows/collect.yml`). Cron é
  **best-effort** (atrasos de 5-30min são normais); nosso desenho tolera cadência
  irregular porque a trajetória usa timestamps reais — degrada resolução, não
  correção. Gotcha: workflow em repo público **é desativado após 60 dias sem
  atividade** — mitigar com commits de dev ou keepalive; sempre incluir
  `workflow_dispatch`.
- **CI** = `.github/workflows/ci.yml` roda `pytest` a cada push (selo verde).
- **Dashboard** = Streamlit Community Cloud (grátis, deploya do GitHub). Dorme
  após 12h sem visita e tem **~1GB de RAM** — por isso o Motor A roda como replay
  de UMA trajetória por vez (nunca carrega o banco na memória).
- **Storage** = Turso (SQLite na nuvem, acesso HTTP, ideal p/ runner efêmero).
- **Secrets** (`YOUTUBE_API_KEY`, `TURSO_*`) vivem nos Secrets do GitHub/Streamlit,
  **nunca no disco da máquina do trabalho**.

## Princípio-mestre: núcleo append-only sagrado

O storage codifica uma fronteira: **verdade** (`videos`, `snapshots` —
append-only, insubstituível) vs **derivado** (`detections`, `labels`, features —
recomputável a partir da verdade). Consequência operacional: **o coletor jamais
roda código de modelo.** Ele faz uma coisa só (pega stats, persiste) e é blindado
— um bug no detector nunca pode derrubar a coleta, porque o dado perdido não
volta. Todo derivado pode ser dropado e reconstruído dos snapshots.

## A assimetria da cota (por que o coletor é assim)

`search.list` custa 100 unidades (só ~100 buscas/dia); `videos.list` custa 1
unidade e leva 50 IDs por chamada. Logo: **descobrir é caro, amostrar é barato.**
O coletor descobre com parcimônia e amostra com folga. O gargalo nunca é amostrar
— é decidir o que vale a pena rastrear.

## Cadência adaptativa SEM agendador em processo

A inteligência que seria do APScheduler virou uma decisão **sem estado**
(`collect/policy.py`): a cada execução, `select_due()` consulta a carteira no
banco e devolve quem está vencido. Vídeo quente (jovem) tem intervalo curto;
frio, longo; velho demais é aposentado (`retire_stale`). Todo o estado vive no
banco — perfeito para runners efêmeros. O APScheduler sobra apenas para um
`collect --daemon` local opcional (coleta densa manual quando a máquina está no
ar).

## Composição: contratos ↔ implementações reais

O **composition root** (`composition.py`) é o único módulo que conhece todas as
peças concretas. Ele monta o grafo a partir das settings:

- `Clock` → `SystemClock` (UTC).
- `YouTubeClient` → `YouTubeApiClient` (adaptador real; distingue 403 quotaExceeded
  de 429 rateLimited; import preguiçoso do cliente Google).
- `TrajectoryRepository` → `SqlTrajectoryRepository` sobre uma conexão que a
  fábrica (`storage/connection.py`) escolhe: **Turso se configurado, senão SQLite
  local WAL**. O repositório é idêntico nos dois — a troca dev↔prod é só a conexão.

Os testes têm o seu próprio composition root (os fixtures com fakes), por isso
nada de produção aparece na suíte.

## Pontos de entrada (CLI Typer)

    breakout initdb                 aplica o schema (idempotente)
    breakout discover --query "..." descobre vídeos e semeia a carteira (gasta search)
    breakout collect --once         amostra os vencidos (o que o GitHub Actions chama)
    breakout detect                 job offline: roda detectores, grava detecções
    breakout dashboard              sobe o Streamlit (replay ao vivo do Motor A)

`python -m breakout ...` é equivalente (usado pelo CI/coletor).

## Ciclos de vida (resumo)

| Processo   | Onde                  | Vida            | Escreve?          |
|------------|-----------------------|-----------------|-------------------|
| Coletor    | GitHub Actions (cron) | efêmero/rodada  | só a verdade      |
| Jobs (detect/features/train) | GitHub Actions ou local | batch sob demanda | só derivado |
| Dashboard  | Streamlit Cloud       | sob visita      | nada (read-only)  |
| CI         | GitHub Actions        | por push        | nada              |

## Instalação (dev, sem admin)

    python -m venv .venv && . .venv/bin/activate    # ou: uv venv
    pip install -e ".[dev]"     # núcleo + ferramentas de teste
    pytest -q                   # tudo verde
    # produção adiciona: pip install -e ".[prod]"  (google-api + libsql — NÃO
    # instala no Windows sem admin; roda via GitHub Actions, nunca localmente)
    # dashboard local: pip install -e ".[dashboard]"  (streamlit — funciona no
    # Windows, testa contra SQLite local sem precisar de [prod])
