# Planejamento — Reconhecimento facial na thumbnail (rede neural)

> Registrado em 2026-08-25. Ainda não implementado. Retomar seguindo
> test-first (Princípio 4 do CLAUDE.md): escrever os testes da seção
> "Testes" abaixo ANTES de tocar em código de produção.

## Contexto

A Fase 5 (`thumbnail.py`) descartou contagem de rosto porque o
`opencv-python` 5.x removeu o `CascadeClassifier` (Haar cascade) clássico —
só sobrou `cv2.FaceDetectorYN`, baseado numa rede neural (YuNet), que exige
um arquivo de modelo `.onnx` à parte. Na época isso pareceu contradizer a
decisão de evitar download pesado de modelo (o mesmo motivo de usarmos
legenda em vez de Whisper). O usuário revisitou essa decisão e pediu pra
aprofundar o reconhecimento facial via rede neural, removendo essa restrição.

**Achado importante que muda o cálculo de custo/benefício:** o modelo YuNet
é **pequeno** (~1-2MB), publicado oficialmente no
[opencv_zoo](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)
do GitHub. Não é comparável a Whisper (que precisa de torch + download de
áudio/vídeo). "Tirar a restrição de download pesado" aqui é um pouco
enganoso — o modelo em si é leve; o que a Fase 5 evitou foi a complexidade
de gerenciar mais um asset binário no projeto, não peso computacional real.

## Decisão de empacotamento

Baixar o `.onnx` **uma vez**, durante a implementação, e commitar no repo
como package data:

```
src/breakout/engine_b/models/face_detection_yunet.onnx
```

com entrada correspondente em `[tool.setuptools.package-data]` no
`pyproject.toml` (mesmo padrão que `schema.sql` já usa via
`importlib.resources` em `sql_repository.py`). Isso evita depender de rede
em runtime (GitHub Actions é efêmero; Streamlit Cloud reinicia o container)
só para buscar o modelo — mais robusto e mais rápido que baixar a cada cold
start.

## Implementação

- `src/breakout/engine_b/thumbnail.py`: readicionar `thumb_face_count` em
  `_features_from_image`. API esperada (**confirmar a assinatura exata na
  versão instalada antes de codar** — `cv2.__version__`, a API do OpenCV 5.x
  é recente e pode diferir de exemplos antigos):
  ```python
  detector = cv2.FaceDetectorYN.create(model_path, "", (width, height))
  detector.setInputSize((width, height))
  _, faces = detector.detect(image)
  face_count = 0.0 if faces is None else float(len(faces))
  ```
  Carregar o detector uma vez (padrão lazy-singleton, igual não existia mais
  pro cascade removido — reaproveitar a ideia do `_FACE_CASCADE` antigo, mas
  para o novo detector).
- `pyproject.toml`: adicionar o `.onnx` em
  `[tool.setuptools.package-data]` sob `breakout.engine_b`.
- `CLAUDE.md`: reverter a nota "sem contagem de rosto" na Seção 6 (Motor B)
  e na Seção 12 (Fase 5), explicando a correção de entendimento sobre o
  tamanho do modelo YuNet.

## Testes (escrever ANTES do código)

- `tests/unit/test_thumbnail.py`:
  - Imagem sem rosto (ruído aleatório ou cor sólida, como as que já existem
    no arquivo) → `thumb_face_count == 0.0`.
  - Imagem COM rosto → precisa de um fixture de imagem real (não dá pra
    sintetizar um rosto via numpy). Decisão a confirmar na implementação:
    salvar uma imagem pequena (dezenas de KB), de domínio público (CC0), em
    `tests/fixtures/rosto_exemplo.jpg`, e testar que `thumb_face_count >= 1`.
  - Regressão: `extract_thumbnail_features` continua devolvendo `{}` pra URL
    vazia ou download com falha (não quebrar o contrato já testado hoje).
  - `set(feats)` no teste `test_todas_as_features_esperadas_presentes`
    precisa voltar a incluir `"thumb_face_count"`.

## Riscos / pontos de atenção

- Detectores baseados em rede neural têm falsos positivos/negativos
  diferentes de Haar cascade — não assumir que o número bate com contagem
  manual; é uma métrica honesta ("quantos rostos o detector achou"), não uma
  verdade absoluta (mesma honestidade epistêmica do resto do projeto).
- Carregar o modelo (`FaceDetectorYN.create`) tem custo de I/O na primeira
  chamada — cachear a instância do detector (módulo-level ou
  `st.cache_resource` no dashboard), nunca recriar por imagem.
