# Breakout — Arquitetura de Testes

> Este documento é contexto para o Claude Code. Leia antes de gerar ou alterar
> código de teste. A filosofia aqui **condiciona a arquitetura do projeto
> inteiro**: os contratos de teste são os contratos do sistema.

## Filosofia: test-first como descoberta de arquitetura

Escrever o teste primeiro obriga a nomear um comportamento; escrever o mock/fake
obriga a desenhar uma fronteira. Então cada fake que planejamos vira um
**contrato da arquitetura** e cada teste vira uma **feature candidata**. A camada
de testes não é uma checagem posterior — é a planta baixa.

## As duas naturezas (regra que separa tudo)

O Breakout tem duas naturezas que pedem filosofias de teste diferentes:

- **Engenharia** (coletor, storage, wrapper de API): testa-se do jeito clássico
  — mocka a fronteira, testa a lógica, tudo determinístico e rápido.
  `assert x == y` é legítimo aqui.
- **Ciência** (detectores, classificador): **não** se testa com `assert
  score == 0.73` — sai float de modelo estocástico. Testa-se por **propriedades**
  (`Hypothesis`), **contratos** e **comportamento sobre verdade-conhecida
  sintética**.

Manter essa separação limpa já é meia arquitetura.

## Fake > Mock

Preferimos **fakes** (implementações reais, mas em memória) a **mocks** (stubs
que afirmam "essa função foi chamada 2x"). Mock acopla o teste à implementação e
apodrece. Reservamos mock de verdade só para a fronteira externa real: a **rede**.

| Fronteira        | Estratégia           | Onde                          |
|------------------|----------------------|-------------------------------|
| Rede (YouTube)   | **mock/fake do adaptador** | `tests/fakes/youtube.py` |
| Relógio          | **fake** (avançável) | `tests/fakes/clock.py`        |
| Storage          | **fake** em memória  | `tests/fakes/repository.py`   |
| Trajetória       | **gerador sintético**| `src/breakout/synth/`         |

**Nunca mocke o `google-api-python-client` diretamente** (usa `httplib2`, é
horrível de interceptar). Envolva a API num adaptador fino (`YouTubeClient`) e
mocke o adaptador. A interface enxuta já expõe as features da fronteira: cota,
paginação, retry, vídeo deletado/privado.

## Os contratos (`src/breakout/contracts.py`)

Quatro Protocols. Cada um é alvo de fake **e** contrato da implementação real:

- `Clock` — `now()`. Tempo é dependência injetada, nunca `datetime.now()` solto.
- `YouTubeClient` — `search_recent / fetch_stats / fetch_metadata`. O adaptador.
- `TrajectoryRepository` — `save_snapshot / save_metadata / get_trajectory /
  video_ids`. O storage.
- `Detector` — `update(t, views) -> Detection | None` + `reset()`. O contrato
  **online** do Motor A: baseline, CUSUM, Kleinberg e BOCPD são implementações
  intercambiáveis do mesmo Protocol — é o que permite o *bake-off*.

## A peça-chave: verdade-conhecida sintética (`src/breakout/synth/`)

O ativo de teste de maior alavancagem. Gera curvas de views-no-tempo com ponto de
decolagem **rotulado** e teto **conhecido**. Isso:

- dá **lead time exato** (você sabe onde foi a decolagem);
- roda **todos os detectores contra as mesmas curvas** (bake-off maçã-com-maçã);
- **desbloqueia o Motor A inteiro na Fase 0**, sem esperar o coletor acumular;
- valida o **Motor B** pelo mesmo truque: planta um sinal conhecido ("número no
  título → 3x viral, por construção") e o teste afirma que o modelo o encontra.

Vive em `src/` (não em `tests/`) porque também é feature: alimenta o modo
replay/simulação e os demos do README.

### Os cinco arquétipos (cada um estressa o detector de um jeito)

| Arquétipo      | Fenômeno                        | O que testa                       |
|----------------|---------------------------------|-----------------------------------|
| `ROCKET`       | decola quase no upload          | detecção sob subida abrupta       |
| `SLOW_BURN`    | sobe devagar, estoura tarde     | sinal fraco por muito tempo       |
| `SLEEPER`      | morto por dias, depois acorda   | change point tardio e abrupto     |
| `FLASH_IN_PAN` | sobe rápido e murcha            | **resistência a alarme falso**    |
| `STILLBORN`    | nunca sai do chão               | a taxa-base / o controle          |

Modelo: cada arquétipo é uma logística cumulativa; geramos incrementos ≥ 0, ruído
multiplicativo lognormal (sempre positivo) e `cumsum` → **views monótona por
construção**. Determinístico dado o `seed`.

## O harness e a métrica (`src/breakout/engine_a/`)

- `replay.run_detector(detector, traj)` — reproduz a trajetória ponto-a-ponto e
  devolve a **primeira** detecção (semântica de detecção precoce). É teste e é o
  "modo simulação" do dashboard.
- `metrics.lead_time_hours(...)` — o **pulo do gato**: quantas horas antes do
  cruzamento do limiar viral o detector disparou. Positivo = detectou antes.

## O teste-guarda anti-vazamento

`tests/unit/test_no_leakage.py` trava `engine_b/windows.py::window_before`:
toda feature do Motor B só pode enxergar pontos **até** o instante de rotulagem.
Data leakage é o erro nº 1 de ciência de dados; ter uma barreira estrutural
contra ele é exatamente o que impressiona em entrevista.

## O que está pronto vs. pendente (test-first)

- **Implementado e verde:** gerador sintético, fakes (clock/repo/youtube),
  coletor, harness de replay, métrica de lead time, `BaselineDetector`
  (aceleração — Camada 1 do plano), janela anti-vazamento.
- **Contrato pronto, implementação pendente (`xfail`):** `CusumDetector` (Fase 2),
  `KleinbergBurstDetector` (Fase 3). Quando você implementar na IDE, o `xfail`
  vira `XPASS` e te avisa que ficou pronto.

## Como rodar

```bash
pip install -e ".[dev]"      # deps de teste
pytest                       # tudo, menos os testes de rede (padrão)
pytest -m unit               # só unidade (rápido, dia a dia)
pytest -m integration        # pipeline costurado, ainda offline
pytest --cov=breakout        # com cobertura
```

Marcadores: `unit`, `integration`, `network` (desligado por padrão), `slow`,
`benchmark`. Rede fica **fora** do run padrão (`addopts = -m 'not network'`).

## O leque de funcionalidades que emergiu (cada uma nasceu de um teste)

- **Bake-off de detectores** — CUSUM/Kleinberg/BOCPD na mesma bateria, com placar
  de lead time (`synth.make_batch` já entrega a bateria).
- **Modo replay/simulação** — `run_detector` alimentando a curva "ao vivo".
- **Amostragem adaptativa de cota** — coletar vídeo quente com mais frequência.
- **Definição de "viral" plugável** — limiar vs percentil-por-categoria; abre
  análise de sensibilidade do rótulo.
- **Função de custo tunável** — priorizar antecedência × acurácia.
- **Harness de ablação de features** — ligar/desligar grupos no Motor B.
- **Export de dataset congelado** — reproduzível, para README/relatório.
