# Planejamento — Automação do `discover` (multi-nicho + idioma)

> Registrado em 2026-08-25. Ainda não implementado. Retomar seguindo
> test-first (Princípio 4 do CLAUDE.md): escrever os testes da seção
> "Testes" abaixo ANTES de tocar em código de produção.

## Contexto e escopo confirmado

Hoje `discover` é 100% manual (`workflow_dispatch` com um `--query` digitado
na mão) — decisão original do Princípio 7 ("descobrir é caro, amostrar é
barato"): quem decide quando gastar cota é o dev. O usuário pediu pra
automatizar, e **perguntado diretamente sobre qual termo usar sozinho,
respondeu que quer poder escolher MAIS DE UM nicho, e também o idioma** —
não um termo fixo único. Isso muda o design de "um `--query` no cron" para
"uma lista configurável de (nicho, idioma)".

## Configuração multi-nicho + idioma

Arquivo de config **versionado no repositório** (não é secret — não é dado
sensível, é configuração de produto, deve ser revisável via PR como
qualquer outra decisão do projeto): `discover_topics.yml` na raiz.

```yaml
topics:
  - query: "valorant"
    language: "pt"
  - query: "..."
    language: "en"
```

**A lista exata de nichos/idiomas iniciais fica pra quando o usuário
decidir** — é conteúdo de produto (o que o Breakout rastreia), não uma
decisão técnica; não adivinhar isso na implementação, perguntar/confirmar
com o usuário nesse momento.

## Contrato estendido: idioma na busca

`search_recent` ganha parâmetro opcional `language: str | None = None`:

- `src/breakout/contracts.py` (`YouTubeClient` Protocol).
- `src/breakout/collect/youtube_api.py` (`YouTubeApiClient`): mapear
  `language` pro parâmetro `relevanceLanguage` da `search.list`. **Limitação
  honesta a documentar no docstring:** `relevanceLanguage` só influencia
  RELEVÂNCIA dos resultados, não filtra estritamente por idioma — é a única
  opção que a Data API oferece pra isso.
- `tests/fakes/youtube.py` (`FakeYouTubeClient`): aceitar o parâmetro novo
  sem quebrar a assinatura existente (mesmo comportamento — só precisa
  registrar a chamada em `self.calls` incluindo o idioma, pra testes que
  quiserem checar isso).

## CLI e workflow

- Novo comando `breakout discover-all` (nome a confirmar na implementação):
  lê `discover_topics.yml`, chama a lógica de descoberta uma vez por tópico
  — reaproveitando o máximo de código com o comando `discover` existente
  (que continua igual, pro uso manual/ad-hoc de um termo avulso).
- `.github/workflows/discover.yml`: adicionar `schedule:` (cron diário,
  horário fora de pico tipo `17 3 * * *` — mesma lógica de evitar `:00` que
  o `collect.yml` já usa) **além** do `workflow_dispatch` já existente. O
  job escolhe o comando pelo tipo de evento:
  - `github.event_name == 'schedule'` → `python -m breakout discover-all`
  - `workflow_dispatch` → comportamento atual (`--query`/`--max-results`
    dos inputs), preservando 100% do fluxo manual que já funciona hoje.

## Orçamento de cota

Cada tópico = 100 unidades (`search.list`). Mesmo com ~10 tópicos
configurados, 1000 unidades/dia é ~10% do orçamento diário padrão (10.000
unidades) — folga confortável mesmo rodando a lista inteira todo dia
(Princípio 7 continua respeitado: o "gasto automático" é pequeno e prático
de auditar olhando o tamanho de `discover_topics.yml`).

## Testes (escrever ANTES do código)

- `search_recent` com `language`: `FakeYouTubeClient` grava a chamada com o
  parâmetro; revisão de `youtube_api.py` confirma que
  `relevanceLanguage` é incluído na chamada real (sem teste de rede direto —
  mesmo padrão já estabelecido pro resto do adaptador).
- Parsing de `discover_topics.yml`: função pura, testável sem rede — lista
  vazia, tópicos malformados (erro claro na leitura, não crash silencioso
  nem tópico ignorado sem aviso), tópico sem `language` (cai pra `None`,
  compatível com o parâmetro opcional acima).
- `discover-all` orquestrando N tópicos: via `FakeYouTubeClient`, confirmar
  que roda uma vez por tópico da lista e agrega o total semeado no
  `typer.echo` final (mesmo estilo do `discover` atual).

## Riscos / pontos de atenção

- Rodar automaticamente todo dia significa a carteira de vídeos cresce sem
  supervisão manual — confirmar que `retire_after_h` (política de cadência,
  `policy.py`) já dá conta de aposentar vídeos velhos, evitando a tabela
  `videos`/carteira ativa crescer sem limite.
- Se dois tópicos da lista buscarem os mesmos vídeos (nichos sobrepostos),
  `save_metadata`/`INSERT OR REPLACE` já é idempotente — não deve duplicar,
  mas vale confirmar com um teste se isso importar na prática.
