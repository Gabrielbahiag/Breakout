# Planejamento — Transcrição via Whisper (fallback)

> Registrado em 2026-08-25. **Fechado em 2026-08-26** (test-first: os testes
> da seção "Testes" abaixo foram escritos e confirmados falhando ANTES do
> código de produção existir).

## Contexto e escopo confirmado

A Fase 5 decidiu usar legenda do YouTube (`transcript_api.py`) em vez de
Whisper, pra evitar baixar áudio/vídeo e rodar um modelo pesado. O usuário
pediu pra aprofundar em Whisper também — mas **perguntado diretamente,
confirmou que Whisper deve ser FALLBACK**, não substituto: só roda quando o
vídeo não tem legenda nenhuma (`fetch_transcript_text` devolve `None`).
Mantém o caminho barato (legenda, grátis, sem download de mídia) como
primeira tentativa sempre; só paga o custo pesado quando não tem opção mais
barata.

## Escolha de biblioteca

**`faster-whisper` (CTranslate2), não `openai-whisper`.** `openai-whisper`
depende de `torch` (centenas de MB, lento em CPU sem GPU) — o GitHub Actions
free tier não tem GPU, então rodar o Whisper original ali seria
desproporcionalmente lento. `faster-whisper` entrega a mesma qualidade de
transcrição sem a dependência de torch, com inferência em CPU
significativamente mais rápida.

Modelo: começar com `tiny` ou `base` (os menores) — decisão final de
tamanho fica pra quando testar qualidade real na implementação (trade-off
velocidade × acurácia da transcrição).

## Pipeline

1. Baixar SÓ o áudio do vídeo via `yt-dlp` (formato leve, tipo m4a/webm —
   nunca o vídeo inteiro).
2. Rodar `faster-whisper` sobre o áudio baixado, extrair o texto.
3. Apagar o arquivo de áudio temporário — nunca persistir mídia, só o texto
   vai pro banco (mesmo destino de `VideoMetadata.transcript`, campo que a
   Fase 5 já criou — nenhuma mudança de schema pro texto em si).

`ffmpeg` já vem pré-instalado nos runners `ubuntu-latest` do GitHub Actions
(confirmar no início da implementação) — não deve precisar de setup extra
no workflow.

## Implementação

- `src/breakout/collect/whisper_transcribe.py` (novo módulo): função
  `transcribe_via_whisper(video_id: str) -> str | None` — adaptador fino,
  mesmo espírito de `transcript_api.py`/`youtube_api.py`: best-effort, nunca
  levanta (`except Exception: return None`), sinal de "não deu" é `None`,
  não uma exceção que derruba `discover`.
- `src/breakout/cli.py::discover()`: depois de tentar
  `fetch_transcript_text(video_id)`, se vier `None` E o fallback estiver
  habilitado (ver flag abaixo), tenta `transcribe_via_whisper(video_id)`.
- **Proveniência (honestidade epistêmica):** considerar coluna
  `transcript_source` (`'caption' | 'whisper' | None`) em `videos` — mesma
  técnica de migração idempotente que `thumbnail_url`/`transcript` já usaram
  (`sql_repository.py::_migrate_add_columns`, guardada por
  `PRAGMA table_info`). Transcrição via Whisper pode ter qualidade/erros
  diferentes da legenda oficial (é uma transcrição de áudio de terceiros,
  não o texto que o criador/YouTube efetivamente publicou) — vale rastrear
  de onde veio, para não misturar as duas fontes silenciosamente ao analisar
  resultados depois.

## Dependências e custo operacional

- `pyproject.toml`: novo extra `[whisper]` (não `[prod]` puro) —
  `yt-dlp`, `faster-whisper`. Fica fora do `[prod]` padrão porque é pesado E
  opcional; instalar em toda rodada de `discover` pagaria esse custo à toa
  nos runs que não precisam.
- `.github/workflows/discover.yml`: novo input opcional
  `usar_whisper_fallback` (bool, default `false`). Só quando `true` o job
  instala `[whisper]` e habilita o fallback no CLI (via env var, ex.
  `BREAKOUT_WHISPER_FALLBACK=1`). Mantém o comportamento atual (rápido, sem
  Whisper) como padrão — dado o custo de tempo por vídeo (download de áudio
  + inferência), rodar em TODO discover automático por padrão pode estourar
  o tempo do job em runners grátis; op-in evita essa armadilha até medirmos
  o tempo real por vídeo.

## Testes (escrever ANTES do código)

- `whisper_transcribe.py`: sem teste de rede direto por padrão (mesmo
  padrão de `transcript_api.py`/`youtube_api.py`, Princípio 3 — mockar a
  fronteira externa, não testar o cliente cru). Considerar um teste
  `@pytest.mark.network` opcional (desligado por padrão) que baixa um vídeo
  público minúsculo e conhecido, pra validação manual ocasional quando
  necessário.
- `cli.py::discover()`: teste com `FakeYouTubeClient` + fakes de
  transcript/whisper garantindo que:
  - o fallback Whisper NUNCA é chamado quando a legenda já veio com texto
    (a propriedade "caminho barato primeiro" é o comportamento crítico a
    travar);
  - o fallback só roda quando `usar_whisper_fallback`/env var está
    habilitado — desligado por padrão não deve nem importar o módulo de
    Whisper (evita custo de import em todo `discover` comum).
- Migração de `transcript_source`: mesmo padrão de
  `test_init_schema_migra_colunas_novas_em_banco_ja_existente` (já existe em
  `tests/unit/test_sql_repository.py`, usar como modelo).

## Riscos / pontos de atenção

- Tempo de execução: baixar áudio + transcrever pode levar de segundos a
  dezenas de segundos por vídeo dependendo do tamanho do modelo e duração do
  Short — medir antes de decidir se roda pra todos os vídeos sem legenda de
  uma vez, ou se precisa de um limite por execução (ex: só os N primeiros
  sem legenda, continuando na próxima rodada).
- `yt-dlp` depende do YouTube não ter mudado a forma de servir os vídeos —
  igual `youtube-transcript-api`, é um mecanismo não-oficial e pode quebrar
  entre versões; manter `except Exception` amplo e nunca deixar isso
  derrubar o `discover` inteiro.

## Implementado (2026-08-26)

Exatamente conforme planejado:

- `collect/whisper_transcribe.py`: `transcribe_via_whisper(video_id, *,
  model_size="tiny") -> str | None`. `yt-dlp` baixa só o áudio pra um
  `tempfile.TemporaryDirectory` (apagado automaticamente ao sair do `with`),
  `faster-whisper` (`WhisperModel("tiny", device="cpu", compute_type="int8")`,
  singleton de módulo) transcreve. `except Exception` largo — nunca levanta.
  Sem teste de rede direto (mesmo padrão de `transcript_api.py`), já que
  `[whisper]` não instala neste ambiente (Windows sem admin/`[prod]`).
- `cli.py::_run_discover`: legenda tentada primeiro; só se vier vazia E
  `c.settings.whisper_fallback_enabled` for `True` é que
  `from .collect.whisper_transcribe import transcribe_via_whisper` acontece
  — import de propósito DENTRO do `if`, então com o fallback desligado
  (padrão) as dependências pesadas nem precisam estar instaladas.
  `transcript_source` (`'caption'` | `'whisper'` | `''`) grava a proveniência.
- `Settings.whisper_fallback_enabled: bool = False` (env
  `WHISPER_FALLBACK_ENABLED`) — decisão de nomear sem o prefixo `BREAKOUT_`
  cogitado originalmente no plano, pra ficar consistente com o resto das
  Settings existentes (`YOUTUBE_API_KEY`, `TURSO_*`, nenhuma tem prefixo).
- `VideoMetadata.transcript_source` (novo campo) + coluna `transcript_source`
  em `schema.sql` e `_migrate_add_columns` (mesmo padrão idempotente de
  `thumbnail_url`/`transcript`).
- `pyproject.toml`: novo extra `[whisper]` (`faster-whisper`, `yt-dlp`), fora
  de `[prod]`.
- `discover.yml`: novo input `usar_whisper_fallback` (boolean, default
  `false`) — dois steps de instalação mutuamente exclusivos (`if:
  inputs.usar_whisper_fallback == true` / `!= true`) escolhem `.[prod]` ou
  `.[prod,whisper]`; `WHISPER_FALLBACK_ENABLED: ${{ inputs.usar_whisper_fallback
  == true }}` nos dois steps de `discover`/`discover-all` — a comparação
  `== true` (em vez de repassar o input cru) evita que o `schedule` (cron,
  sem `inputs` definido) vaze uma string vazia pro parser de bool do
  pydantic-settings.

**Testes (`tests/unit/test_discover_whisper_fallback.py`, 4 testes):**
achado de design útil — como `faster-whisper`/`yt-dlp` não estão instalados
neste ambiente de teste, o teste do caminho "fallback desligado" prova a
propriedade "não importa o módulo fora da hora" de graça: se o código
importasse `whisper_transcribe` incondicionalmente, o teste quebraria com
`ModuleNotFoundError` de verdade, não com um mock falhando. Pro caminho
"fallback ligado", em vez de instalar as dependências pesadas só pra testar,
um módulo FALSO é injetado em `sys.modules["breakout.collect.
whisper_transcribe"]` via `monkeypatch.setitem` antes do `import` lazy
acontecer — o `from .collect.whisper_transcribe import
transcribe_via_whisper` dentro de `_run_discover` encontra o módulo já em
cache e nunca toca o arquivo real (nem `faster_whisper`/`yt_dlp`).
