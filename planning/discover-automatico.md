# Automação do `discover` (multi-nicho + idioma)

> ✅ Implementado em 2026-08-26. Este arquivo é o registro histórico da
> decisão — o design mudou durante a execução (ver "Correção de design"
> abaixo) porque o usuário deu um detalhe novo que não tinha no planejamento
> original: quer editar os nichos **pelo próprio dashboard**, não só por
> arquivo versionado no repo.

## Contexto e escopo confirmado

`discover` era 100% manual (`workflow_dispatch` com um `--query` digitado na
mão) — decisão original do Princípio 7 ("descobrir é caro, amostrar é
barato"): quem decide quando gastar cota é o dev. O usuário pediu pra
automatizar e, perguntado sobre qual termo usar sozinho, respondeu que quer
poder escolher MAIS DE UM nicho e também o idioma — não um termo fixo único.

## Correção de design: banco, não arquivo

O plano original (ver histórico do commit) sugeria `discover_topics.yml`
versionado no repo, editável via PR. **Isso mudou**: perguntado sobre onde
editar os nichos, o usuário especificou que quer trocar nicho/palavra-chave e
idioma **direto da tela do dashboard**, a qualquer hora, sem depender de
commit/deploy. Um arquivo em git não permite isso (editar exigiria PR +
merge + redeploy do Streamlit Cloud) — a implementação final usa uma tabela
nova no banco (`discover_topics`), com uma seção no dashboard pra
adicionar/pausar/remover nichos.

Isso introduziu uma exceção documentada ao princípio "dashboard é read-only"
(Seção 5 do CLAUDE.md): `discover_topics` é a ÚNICA tabela que o dashboard
tem permissão de escrever — justificado porque não é dado coletado (não
arrisca o núcleo append-only sagrado), é preferência operacional de produto.

## O que foi implementado

- **`src/breakout/storage/schema.sql`**: tabela `discover_topics` (`id`,
  `query`, `language`, `active`, `created_at`) — `CREATE TABLE IF NOT
  EXISTS`, sem migração especial (tabela nova, não mexe em `videos`).
- **`src/breakout/collect/topics.py`** (novo): `list_topics`, `add_topic`,
  `remove_topic`, `set_active` — funções diretas sobre a conexão (mesmo
  estilo de `collect/policy.py`), fora do contrato `TrajectoryRepository`
  (não é sobre trajetórias).
- **`src/breakout/contracts.py` + `collect/youtube_api.py` +
  `tests/fakes/youtube.py`**: `search_recent` ganhou `language: str | None`,
  mapeado pro `relevanceLanguage` da `search.list` (dica de relevância, não
  filtro estrito — limitação documentada no docstring do Protocol).
- **`src/breakout/cli.py`**: lógica de descoberta extraída pra
  `_run_discover()` (compartilhada), comando `discover` preservado (uso
  manual/ad-hoc, ganhou `--language` opcional) e novo comando `discover-all`
  (lê `discover_topics`, roda uma vez por nicho ATIVO).
- **`.github/workflows/discover.yml`**: ganhou `schedule:` (cron diário
  `17 3 * * *`) além do `workflow_dispatch` já existente. Disparo manual COM
  `query` preenchido → comportamento antigo (um termo avulso); disparo manual
  SEM `query`, ou cron → `discover-all` (todos os nichos ativos).
- **`src/breakout/dashboard.py`**: seção nova na sidebar ("Nichos do discover
  automático", expander no topo) — lista os nichos (ativos riscados quando
  pausados), botões pausar/reativar/remover, formulário pra adicionar
  (`query` + `language` opcional). Refatorado `_repo()`/`_connection()` pra
  derivar de um `_container()` cacheado (evita duas conexões separadas).

## Testes (escritos antes de fechar a mudança)

- `tests/unit/test_topics.py` — 8 testes: roundtrip add/list, query vazia
  levanta, tira espaço nas bordas, remove, pausa/reativa, lista vazia.
- `tests/unit/test_youtube_api.py` — 2 testes: `relevanceLanguage` só entra
  na chamada real quando `language` é passado (stub do `_service()`, não do
  `google-api-python-client` cru).
- `tests/unit/test_dashboard.py` — 3 testes via `streamlit.testing.v1.AppTest`
  contra SQLite temporário: sobe sem exceção, adiciona/pausa/remove nicho
  pela UI, e um teste específico provando que o nicho persiste ENTRE
  instâncias do `AppTest` (é banco, não `session_state`).
- `cli.py` (`discover`/`discover-all`) permanece sem teste direto — mesmo
  padrão já estabelecido pro resto do CLI (orquestração fina sobre peças já
  testadas isoladamente).

## Pendências / próximos passos

- **A lista de nichos em si fica vazia até o usuário adicionar pelo
  dashboard** (ou via SQL direto) — nada foi semeado automaticamente.
- Orçamento de cota: cada nicho ativo = 100 unidades (`search.list`) por
  execução do cron. Folga confortável mesmo com muitos nichos (Princípio 7).
- Risco já observado no plano original ainda vale: `retire_after_h`
  (`policy.py`) precisa continuar dando conta de aposentar vídeos velhos
  conforme a carteira cresce com descoberta automática ligada.
