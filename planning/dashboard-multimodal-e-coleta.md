# Planejamento — Dashboard: conectar multimodal + disparar coleta

> Registrado em 2026-08-25. **Parte 1 fechada em 2026-08-26** (test-first:
> `tests/unit/test_dashboard_multimodal.py` escrito antes do código,
> confirmado falhando, depois implementado até ficar verde). Parte 2 (GitHub
> API dispatch) ainda não implementada — retomar seguindo test-first
> (Princípio 4 do CLAUDE.md): escrever os testes da seção "Testes" abaixo
> ANTES de tocar em código de produção.

Duas partes que ficam juntas por serem ambas mudanças de UI no
`dashboard.py`, mas são independentes uma da outra — dá pra implementar só
a Parte 1 sem a Parte 2, ou vice-versa.

## Parte 1 — conectar multimodal ao dashboard ✅ FECHADA

### Contexto

`dashboard.py` (modo "Dados reais") já chama `extract_features(...,
with_multimodal=False)` — as features de thumbnail/transcrição existem no
Motor B desde a Fase 5, mas nunca aparecem na tela hoje.

### Implementação

- Checkbox na sidebar (ou perto da seção do Motor B): "Incluir features
  multimodais (baixa a thumbnail)" — **desligado por padrão**, mesmo motivo
  de `with_multimodal=False` ser o padrão em `features.py` (baixar a imagem
  a cada rerun do Streamlit seria caro/imprevisível se ligado sozinho).
- Quando ligado:
  - `st.image(metadata.thumbnail_url)` — mostrar a imagem de verdade, não só
    os números extraídos dela.
  - As features de CV (`thumb_brightness`, `thumb_saturation`,
    `thumb_colorfulness`, `thumb_edge_density`, e `thumb_face_count` se o
    plano de reconhecimento facial já tiver sido implementado).
  - O texto da transcrição (ou um trecho, se for longo — decidir um limite
    de caracteres exibidos) + `transcript_source` (Plano B de Whisper) se
    essa coluna já existir.
  - Chamar `extract_features(..., with_multimodal=True)` só quando o
    checkbox estiver marcado, nunca antes.

### Testes (escrever ANTES do código)

- `streamlit.testing.v1.AppTest` com o checkbox desligado (padrão): sem
  exceção, sem chamada de rede (mesmo espírito do teste já existente
  `test_multimodal_desligado_por_padrao_nao_toca_rede` em
  `tests/unit/test_features.py`, mas na camada do dashboard).
- `AppTest` com o checkbox ligado, mockando o download da thumbnail via
  `respx` (mesmo padrão de `tests/unit/test_features.py`) — confirma que
  liga sem exceção e que a imagem/features aparecem.

### Implementado (2026-08-26)

Exatamente como planejado: checkbox "Incluir features multimodais (baixa a
thumbnail)" desligado por padrão na seção do Motor B; quando ligado, mostra
`st.image(metadata.thumbnail_url)`, a tabela de features (incluindo as
multimodais) e um trecho da transcrição (até 500 caracteres). Três testes em
`tests/unit/test_dashboard_multimodal.py` (checkbox desligado sem rede;
ligado com download mockado via `respx`; ligado com download falho não
quebra o dashboard).

**Achado não-óbvio que custou uma sessão de debug:** o helper de teste
`_multimodal_checkbox` procurava `"multimodal" in label.lower()`, mas o
texto real do checkbox está em português — "multimodai**s**". Como o plural
troca "modal" por "modais" (o `l` vira `i` antes do `s`), a string
"multimodal" (singular) NUNCA é substring de "multimodais". O sintoma era
um `StopIteration` que parecia um bug do `AppTest`/pytest (funcionava em
scripts manuais de debug, falhava só dentro do teste real) — mas os scripts
de debug só *imprimiam* a lista de labels pra inspeção visual, nunca
avaliavam de fato a expressão `"multimodal" in ...`, então pareciam
confirmar que o checkbox "existia" sem nunca testar o match que realmente
falhava. Lição: ao depurar um `next(gen)` que estoura `StopIteration`,
materialize o gerador em lista E imprima o resultado booleano de CADA
condição do filtro — não só os valores que estão sendo filtrados — antes de
suspeitar do framework de teste. Corrigido trocando o filtro para
`"multimoda" in label.lower()` (cobre singular e plural).

## Parte 2 — disparar coleta pelo dashboard (via GitHub API)

### Contexto e decisão confirmada

**O usuário confirmou que quer isso**, via API do GitHub — não escrita
direta no banco. Isso preserva o princípio "dashboard é read-only" da Seção
5 do CLAUDE.md: o dashboard não ganha uma forma nova de tocar o Turso, ganha
uma forma de pedir pro GitHub Actions tocar o Turso por ele — exatamente
como um clique manual em "Run workflow" já faz hoje, só que a partir da
própria tela do dashboard.

### Implementação

- **Secret novo:** um GitHub Personal Access Token **fine-grained**, escopo
  `Actions: write` restrito a ESTE repositório (nunca um token clássico
  amplo) — guardado como secret do app Streamlit (nome sugerido:
  `GITHUB_DISPATCH_TOKEN`), nunca no `.env` local nem no código. Documentar
  em `CLAUDE.md` Seção 10 o passo a passo de geração (GitHub → Settings →
  Developer settings → Fine-grained personal access tokens → repositório
  específico → permissão "Actions: Read and write").
- **Mecanismo:** `POST /repos/{owner}/{repo}/actions/workflows/
  {workflow_id ou nome do arquivo}/dispatches` via `httpx` (já dependência
  core), com o token no header `Authorization: Bearer <token>` e `ref` (a
  branch, `main`).
- **UI:** botões na sidebar — "Disparar collect agora" e "Disparar discover
  agora" (este pode reusar `discover_topics.yml` do Plano C em vez de pedir
  um `query` avulso no dashboard, mantendo consistência com o que roda
  automaticamente).
- **Feedback:** a API de dispatch só confirma que o evento foi ENFILEIRADO,
  não devolve o resultado do workflow. Mostrar `st.success` com um link pra
  aba Actions do repo — nunca fingir que sabemos se a coleta funcionou só
  porque o dispatch foi aceito.
- **Ausência do secret:** mensagem de erro clara na UI (ex: "Secret
  `GITHUB_DISPATCH_TOKEN` não configurado — veja Seção 10 do CLAUDE.md"),
  nunca uma exceção crua estourando a tela.

### Testes (escrever ANTES do código)

- Função pura que monta a chamada HTTP de dispatch (URL, headers, payload) —
  testável sem rede real, mockando `httpx.post` via `respx`. Confirma URL
  correta (owner/repo/workflow certos), header de autorização presente,
  payload com o `ref` certo.
- Cenário "secret ausente": a função/UI devolve uma mensagem clara, não
  levanta exceção não tratada.
- `AppTest`: clicar no botão dispara a chamada mockada (via `respx`) e o
  `st.success`/`st.error` aparece conforme o resultado mockado (sucesso vs.
  falha HTTP).

### Riscos / pontos de atenção

- **Este é o primeiro secret do projeto com poder de ESCRITA de verdade**
  (Turso e YouTube API key são credenciais de DADOS; um GitHub PAT com
  escopo Actions pode disparar qualquer workflow do repo, não só
  collect/discover). Reforçar escopo mínimo (fine-grained, só Actions, só
  este repo) e nunca reusar esse token pra outra finalidade.
- Rate limiting: a API do GitHub tem limite de requisições — não é
  preocupação real pro volume de cliques que um dashboard pessoal geraria,
  mas vale um comentário no código explicando que não há retry automático
  (clique manual do usuário já serve de "retry").
