# TASKS — motor antifraude Pix (hackathon QI Tech)

Relógio: início 01:15 · checkpoint 03:00 · checkpoint 05:30 · **code freeze 08:00** · entrega 12:00 (repositório no Slack) · apresentação 13:00.
Fluxo de trabalho: seção "Fluxo de trabalho do time" do `CLAUDE.md`. Estados: `a fazer` · `fazendo` · `em revisão` · `pronto` · `cortado`.
Cada pessoa só edita a linha da própria tarefa neste arquivo (no próprio PR). Prompts prontos das tarefas da Victoria e da Natalia: `docs/tarefas/<ID>.md`.

Arquivos de contrato (só o Ramon altera): `database/database.sql`, `src/engine/risk_context.py`, `src/engine/policy.py`, `src/schemas/post_pix_transaction.json`, `CLAUDE.md`, `docs/catalogo-de-erros.md`.

## Quadro

### P0 — sem isso não há demo nem nota

| ID | Tarefa | Cx | Dono | Revisor | Depende de | Est. | Limite | Estado |
|---|---|---|---|---|---|---|---|---|
| T01 | Contrato do motor: `TriggeredRule` com `observed`/`threshold` dict + `description`/`translation`; `EngineResult` com a lista de regras avaliadas (`fired`/`not_fired`/`unavailable`) | ALTA | Ramon | Victoria | — | 20 | 01:40 | em revisão |
| T02 | Scaffold copiado do `banco/` (Docker, compose, requirements, CI, errors, utils, middlewares, harness) | BAIXA→Ramon | Ramon (Wren) | Victoria | — | 50 | 02:10 | em revisão |
| T03 | Esqueleto do motor + molde: `policy.py`, `evaluate`, matriz, pisos, confiança, cold start, fases, regra-molde `HOW_NIGHT_LIMIT_EXCEEDED` | ALTA | Ramon (Chaz) | Victoria | T01 | 50 | 02:30 | a fazer |
| T04 | README: esqueleto exato do modelo + "Como o motor de decisão funciona" + "Como as regras viram decisão" + cabeçalho e formato da tabela de Regras | ALTA | Ramon (Hann) | Victoria | — | 40 | 02:00 | em revisão |
| T05 | `POST /pix/transaction` com motor de mentira: resource, controller, repositories de gravação (titular, conta, Pix, análise, 3 eixos), DTO, formato do `metadata`, **e os 15 models, guiados pelos testes** | MÉDIA | Victoria | Ramon | T01, T02 | 140 | 03:45 | a fazer |
| T06 | ~~Models SQLAlchemy~~ absorvido pelo T05: os 15 models nascem dos testes do POST (sem teste próprio, não há ciclo TDD) | — | Victoria (no T05) | Ramon | — | 0 | — | cortado |
| T07 | `GET /pix/transaction/{id}` (200 / 404 `RNV001039`) + seção `## Contrato da API` do README | MÉDIA | Victoria | Ramon | T05 | 30 | 03:30 | a fazer |
| T08 | Regras WHERE do payload: `WHERE_DESTINATION_NEW_ACCOUNT`, `WHERE_UNKNOWN_PARTICIPANT` | BAIXA | Natalia | Ramon | T03 | 40 | 03:30 | a fazer |
| T09 | Idempotência com concorrência: `IntegrityError` → rollback → hash → 200 / 422 `RNV001024`; 10x o mesmo `id` → uma análise | ALTA | Ramon (Chaz) | Victoria | T05 | 45 | 04:15 | a fazer |
| T10 | Motor real no controller: `RiskContext` montado do payload (flow, idades, listed, IP privado), `evaluate`, gravação de `pix_analysis_rule` (todas as regras avaliadas) | ALTA | Ramon (Chaz) | Victoria | T03, T05 | 60 | 04:30 | a fazer |
| T11 | Testes de integração dos erros de formato: 400 (`RNV000001`, `RNV000007`–`010`) e 403 `RNV000002` no POST e no GET | BAIXA | Natalia | Victoria | T05, T07 | 40 | 04:15 | a fazer |
| T12 | Validações de sentido: 422 `RNV001002`, `RNV001020`, `RNV001040`–`043`; 409 `RNV001044` | MÉDIA | Victoria | Ramon | T07 | 70 | 04:45 | a fazer |
| T13 | Teste de integração: payload de exemplo do desafio → `rejected` (`two_suspicious_axes`) | BAIXA | Natalia | Victoria | T03, T05 | 20 | 04:30 | a fazer |
| T14 | Regras WHERE de histórico: `WHERE_DESTINATION_FAN_IN` (critical, por fluxo), `WHERE_DESTINATION_REJECTIONS` (critical, fundada suspeita) | BAIXA | Natalia | Ramon | T08 | 45 | 05:15 | a fazer |
| T15 | Consultas de janela que montam o `RiskContext` (velocity, soma noturna, soma de device novo, docs por device, fan-in, rejeições no destino, pagadores por IP) | ALTA | Ramon (Chaz) | Victoria | T06, T10 | 75 | 05:20 | a fazer |
| T16 | Regras HOW/WHO núcleo: `HOW_VELOCITY_EXCEEDED` (por fluxo, suspicious/critical), `WHO_DEVICE_COMPROMISED` (critical) | MÉDIA | Victoria | Ramon | T03 | 50 | 05:30 | a fazer |
| T17 | README "Como rodar e testar": do clone ao 1º `curl` (com `INTERNAL-TOKEN`), payload do desafio pronto para colar, `pytest`, farm | BAIXA | Natalia | Victoria | T05, T07 | 30 | 05:45 | a fazer |
| T18 | README: exemplo de ponta a ponta (payload do desafio → `rejected`, com o porquê) + revisão da tabela de Regras contra o `policy.py` | ALTA | Ramon (Hann) | Victoria | T13, T08 | 30 | 05:30 | a fazer |
| T29 | Freeze: README testado do zero numa máquina limpa, CI verde, `develop` → `main` | ALTA | Ramon (Wren + Hann) | Victoria | todos P0 | 30 | 08:00 | a fazer |

### P1 — profundidade que a banca avalia

| ID | Tarefa | Cx | Dono | Revisor | Depende de | Est. | Limite | Estado |
|---|---|---|---|---|---|---|---|---|
| T19 | `tests/unit/test_readme_rules.py`: README × `policy.py` (rule_code e valores) | ALTA | Ramon (Chaz) | Victoria | T04, T18 | 30 | 06:15 | a fazer |
| T20 | Memória do motor: `account_device`/`account_counterparty` (só `approved`, incremento atômico), device unknown → observing → trusted, `TRUST_RECURRENT_BENEFICIARY`, `TRUST_MATURE_SELF_PIX` | ALTA | Ramon (Chaz/Rune) | Victoria | T15 | 60 | 07:00 | a fazer |
| T21 | Regras HOW/WHO de profundidade: `HOW_ABOVE_CUSTOMER_CEILING` (fases 0/1/2), `HOW_EARLY_MORNING_AMOUNT`, `HOW_RETRY_AFTER_REJECTION` (sondagem), `HOW_TEST_PIX`, `WHO_DEVICE_UNKNOWN` | MÉDIA | Victoria | Ramon | T16, D4 | 60 | 06:30 | a fazer |
| T22 | Testes de integração obrigatórios do cold start: 1ª transação sem histórico nunca `rejected` sem evidência em 2 eixos | BAIXA | Natalia | Victoria | T10 | 35 | 06:20 | a fazer |
| T23 | Personas + `scripts/farm.py` + relatório de taxas (2FA e rejeição) por `policy_version` | MÉDIA | Victoria | Ramon | T15, T21 | 60 | 07:30 | a fazer |
| T24 | README: `## Modelo de dados`, `## Opções descartadas`, `## Limitações conhecidas` | BAIXA | Natalia | Victoria | T17 | 30 | 06:50 | a fazer |

### P2 — só se sobrar tempo (corta primeiro)

| ID | Tarefa | Cx | Dono | Revisor | Depende de | Est. | Limite | Estado |
|---|---|---|---|---|---|---|---|---|
| T25 | Agravantes WHO de IP e canal: IP com 5+ pagadores/1h, IP privado, canal novo (2+ agravantes → suspicious) | BAIXA | Natalia | Ramon | T21 | 40 | 07:30 | a fazer |
| T26 | Connector de país do IP mockado + fallback `ip_country: "unavailable"` | ALTA | Ramon (Chaz) | Victoria | T10 | 40 | 07:30 | a fazer |
| T27 | Shadow mode (`features.shadow`) | ALTA | Ramon (Chaz) | Victoria | T20 | 40 | 07:30 | a fazer |
| T28 | Agravantes de geolocalização (geo parou de vir, fora do BR, distante + device unknown) | MÉDIA | Victoria | Ramon | T25 | 40 | 07:30 | a fazer |

## Linha do tempo

| Hora | Ramon (integra + ALTA com agentes) | Victoria (MÉDIA) | Natalia (BAIXA) |
|---|---|---|---|
| 01:15 | T01 contrato → T03 motor (Chaz) · T04 README (Hann) em paralelo | T05: testes de integração do POST (red), DTO, resource, controller com motor de mentira | T02 scaffold |
| 02:10 | revisa T02 e T04 assim que chegarem | T05 continua | T13 (red, xfail strict) |
| **02:30–03:15** | **Bloco de revisão R1:** T01, T02, T04, T03, T05 | abre PR do T05 até 03:00 → T07 GET | T08 WHERE do payload |
| 03:15 | T09 idempotência (Chaz) e T10 motor real (Chaz, 2ª worktree) | T07 → T12 validações | T08 → T11 testes 400/403 |
| **04:15–05:00** | **Bloco R2:** T07, T08, T11, T09, T10 · T15 janelas (Chaz) roda em paralelo | T12 → T16 HOW/WHO núcleo | T13 desafio → `rejected` → T14 WHERE histórico |
| 05:00 | T18 README ponta a ponta (Hann) | T16 | T14 → T17 Como rodar |
| **05:30–06:15** | **Bloco R3:** T12, T13, T14, T15, T16, T17, T18 · T19 (Chaz) | T21 HOW/WHO P1 | T22 cold start |
| 06:15 | T20 memória (Chaz/Rune) | T21 → T23 farm | T24 README P1 → T25 (P2) |
| **07:00–07:30** | **Bloco R4:** T19, T20, T21, T22, T24 | T23 | T25 |
| 07:30–08:00 | T29 freeze: máquina limpa (Wren), README (Hann), `develop` → `main` | revisa o README do zero ao lado do Ramon | idem |
| 08:00–11:00 | sem código novo: README final, teste do README do zero, slides, ensaio dos 7 min | idem | idem |

## Checkpoints

| Hora | O que precisa estar verde | Se escorregar, corta (nesta ordem) |
|---|---|---|
| **03:00** | API de pé (T02); POST com motor de mentira (T05 em revisão ou mergeado); molde do motor com testes verdes (T03); README com esqueleto (T04) | GET (T07) passa para 03:30; T11 depois do T12; nada de P1/P2 é tocado |
| **05:30** | motor real integrado (T10); payload do desafio → `rejected` (T13 verde); idempotência (T09); validações (T12); regras-núcleo WHERE/HOW/WHO (T08, T14, T16); README com Regras preenchidas (T18) e "Como rodar" (T17) | P2 inteiro (T25–T28) → T24 → T21 só com `HOW_ABOVE_CUSTOMER_CEILING` → T23 farm sem relatório |
| **08:00** | P0 completo, P1 que deu, README testado numa máquina limpa, `develop` → `main` | o P1 que não estiver mergeado às 07:30 fica de fora e vai para "Limitações conhecidas" |

## Catálogo provisório de `rule_code` (o Ramon confirma no T03, que declara todos em `policy.py`)

| Eixo | `rule_code` | Prioridade | Tarefa |
|---|---|---|---|
| how | `HOW_NIGHT_LIMIT_EXCEEDED` | P0 (molde) | T03 |
| how | `HOW_VELOCITY_EXCEEDED` | P0 | T16 |
| how | `HOW_ABOVE_CUSTOMER_CEILING` · `HOW_EARLY_MORNING_AMOUNT` · `HOW_RETRY_AFTER_REJECTION` · `HOW_TEST_PIX` | P1 | T21 |
| who | `WHO_DEVICE_COMPROMISED` | P0 | T16 |
| who | `WHO_DEVICE_UNKNOWN` | P1 | T21 |
| who | `WHO_AGGRAVATING_SIGNALS` | P2 | T25/T28 |
| where | `WHERE_DESTINATION_NEW_ACCOUNT` · `WHERE_UNKNOWN_PARTICIPANT` | P0 | T08 |
| where | `WHERE_DESTINATION_FAN_IN` · `WHERE_DESTINATION_REJECTIONS` | P0 | T14 |
| floor | `FLOOR_UNREGISTERED_DEVICE` · `FLOOR_NIGHT_LIMIT` | P0 | T03 |
| trust | `TRUST_RECURRENT_BENEFICIARY` · `TRUST_MATURE_SELF_PIX` | P1 | T20 |

Por que o payload do desafio dá `rejected`: PF→PF às 22:15 (-03:00) de R$ 1.500 → `HOW_NIGHT_LIMIT_EXCEEDED` (how suspicious) + destino aberto em 10/10, 7 dias antes → `WHERE_DESTINATION_NEW_ACCOUNT` (where suspicious) → 2 eixos suspeitos → `rejected`. As duas evidências vêm do payload, então o cold start não impede.

## Por pessoa

### Ramon — integra, revisa e faz o merge; ALTA com Wren, Chaz, Rune e Hann
Ordem: T01 → T03 (+ T04 em paralelo) → R1 → T09 + T10 → R2 (T15 em paralelo) → T18 → R3 (T19 em paralelo) → T20 → R4 → T29. P2 (T26, T27) só se R4 terminar antes das 07:20.
- **T01** · arquivos: `src/engine/risk_context.py` · pronto: contrato mergeado em `develop` até 01:40 · README: nenhuma.
- **T03** · arquivos: `src/engine/{__init__,engine,policy,matrix,floors,trust,maturity}.py`, `src/engine/analyzers/{__init__,who,how,where}.py` (who/where vazios, retornando `ok`), `tests/unit/__init__.py`, `tests/unit/engine/{__init__,conftest}.py` (fábrica `make_context(**overrides)`), `tests/unit/engine/test_{matrix,floors,trust,cold_start,maturity,how_night_limit}.py` · pronto: `pytest tests/unit` verde, uma célula da matriz por teste, todos os `rule_code` do catálogo e seus parâmetros declarados em `policy.py` · README: linhas `HOW_NIGHT_LIMIT_EXCEEDED`, `FLOOR_UNREGISTERED_DEVICE`, `FLOOR_NIGHT_LIMIT` (formato que vira o molde).
- **T04** · arquivos: `README.md` · pronto: títulos exatamente iguais ao modelo, na ordem; matriz, pisos, confiança e cold start descritos; seção "Como rodar e testar" com o marcador para o T17 · README: esqueleto + duas seções.
- **T09** · arquivos: `src/repositories/pix_transaction_repository.py` (caminho do insert), `src/controllers/pix_transaction_controller.py` (caminho do insert), `tests/integration/pix_transaction/test_post_idempotency.py` · pronto: retry idêntico → 200 com corpo igual; 10x o mesmo `id` (sequencial e em threads) → uma análise; payload diferente → 422 `RNV001024` · README: `## Contrato da API` (linha do 200/`RNV001024`, combinar com a Victoria).
- **T10** · arquivos: `src/controllers/risk_context_builder.py`, `src/controllers/pix_transaction_controller.py` (troca do motor de mentira), `src/repositories/pix_analysis_rule_repository.py`, `tests/integration/pix_transaction/test_post_decision.py` · pronto: T13 verde; uma linha em `pix_analysis_rule` por regra avaliada · README: nenhuma.
- **T15** · arquivos: `src/repositories/risk_history_repository.py`, `src/controllers/risk_context_builder.py`, `tests/integration/pix_transaction/test_history_windows.py`, `docs/modelo-de-dados.md` (tabela Caminho de acesso) · cada consulta usa o índice covering da linha correspondente (Index Only Scan, `Heap Fetches: 0`); device conta `account_holder` distintos, não contas · pronto: cada campo de histórico do P0 com teste de integração; toda consulta com igualdade indexada + janela ≤ 90 dias anterior ao Pix; `latency_ms` < 100 · README: nenhuma (o "o que conta em cada consulta" entra em "Como as regras viram decisão" no T18).
- **T18** · arquivos: `README.md` (seção "Como as regras viram decisão" + revisão da tabela) · pronto: exemplo de ponta a ponta com o `metadata` real da API.
- **T19** · arquivos: `tests/unit/test_readme_rules.py` · pronto: falha se faltar ou sobrar `rule_code` ou se um valor divergir.
- **T20** · arquivos: `src/repositories/{account_device,account_counterparty}_repository.py`, `src/controllers/pix_transaction_controller.py`, `src/controllers/risk_context_builder.py`, `src/engine/trust.py`, testes de integração e de unidade correspondentes · README: linhas `TRUST_*`.
- **T29** · pronto: clone novo → `docker compose up` → `curl` do README → `pytest` verde; `develop` → `main`.

### Victoria — MÉDIA (Claude Code próprio, prompts em `docs/tarefas/`)
Ordem: **T05 → T07 → T12 → T16** (P0) → T21 → T23 (P1) → T28 (P2).
Primeiro passo (01:15): escrever os testes de integração do POST (red) e o DTO/formatador de `metadata`, usando o harness do `banco/` como referência até o T02 subir.
Depende de: Natalia (T02 scaffold ~02:10, T06 models ~02:50), Ramon (T01 contrato ~01:40, T03 molde ~02:30).
Dependem dela: Ramon (T09, T10 precisam do T05), Natalia (T11, T13, T17 precisam do T05/T07).

### Natalia — BAIXA (Claude Code próprio, prompts em `docs/tarefas/`)
Ordem: **T02 → T06 → T08 → T11 → T13 → T14 → T17** (P0) → T22 → T24 (P1) → T25 (P2).
Primeiro passo (01:15): branch `feat/T02-scaffold`, copiar a infraestrutura do `banco/` do `oberico/desafio_qitech`.
Depende de: Ramon (T03 molde para T08/T14), Victoria (T05/T07 para T11, T13, T17).
Dependem dela: todos (T02 e T06 destravam a API).

## Regra de TDD (vale para toda tarefa de código)
- Cada ciclo (um comportamento observável, ponta a ponta pela interface pública) tem 3 commits: `test(ID): red`, `feat(ID): green`, `refactor(ID)`. A descrição do PR traz a seção "Ciclos TDD" com a saída real do red e do green. Sem ela o PR volta. O protocolo completo está em cada `docs/tarefas/<ID>.md`.
- Teste que passa de primeira (caracterização: T11, T22) só vale depois de quebrar o código de propósito, ver falhar e desfazer.
- T13 é teste de aceitação: nasce vermelho e entra com `xfail(strict=True)`; o T10 remove o marcador.
- Tarefas sem ciclo de teste, por natureza: T17 e T24 (documentação) e a infra do T02. Validação delas é rodar do zero.
- Fila da Natalia mudou: T13 primeiro (não depende de nada e já dá para escrever o red), depois T08 (quando o T03 entrar), T11, T14, T17. O T06 saiu do nome dela.

## Mudanças de 02:30 (revisão do tech lead + índices)
- Schema: `account_holder` (titular separado da conta), `pix_analysis_axis` (1 linha por eixo), `decision_basis` como lookup, `BIGSERIAL`/`BIGINT` nas tabelas de volume, constraints nomeadas.
- `analysis_key` virou `UUID` nativo com `DEFAULT gen_random_uuid()` (era `CHAR(36)`). O UUID continua só como chave pública; a PK e as FKs seguem `BIGINT`.
- Índices de janela agora são *covering* (`INCLUDE`), e o `idx_pix_analysis_status` saiu. Conferido com `EXPLAIN ANALYZE` com 1 milhão de Pix: todas as consultas do caminho síncrono em Index Only Scan, < 0,1 ms.
- Afeta: T05, T06, T07, T12, T15, T16 (prompts em `docs/tarefas/` já atualizados). Regra nova: repository novo adiciona linha na tabela "Caminho de acesso" de `docs/modelo-de-dados.md` no mesmo PR.

## Decisões em aberto

| # | Decisão | Quem responde | Até | Bloqueia |
|---|---|---|---|---|
| D1 | Formato do `TriggeredRule` (dict + `description`/`translation`) e como o `EngineResult` expõe as regras avaliadas (`fired`/`not_fired`/`unavailable`) para o `pix_analysis_rule` | Ramon | 01:40 | T03, T05, T10 |
| D2 | De onde o DTO reconstrói o `metadata` no POST, no retry e no GET. Proposta: `pix_analysis.features` (JSONB) guarda `flow`, `reasons`, `floors`, `trust`, `ip_country`; as colunas dão status, eixos, fase, basis e versão | Ramon | 02:00 | T05, T07 |
| D3 | Lista final de `rule_code` e nomes dos parâmetros (catálogo provisório acima) | Ramon | 02:30 (no T03) | T08, T14, T16, T21 |
| D4 | Parâmetros que o CLAUDE.md não fixa: teto de referência por idade da conta (valores), como calcular o `teto_hist` (máximo? p95?), horário de "madrugada", velocity crítico para PJ, janela do "dia" do device novo (dia local ou 24h corridas), período da soma noturna | Ramon | 05:00 | T21, T15 |
| D5 | Formato da linha da tabela de Regras que o T19 vai ler (proposta: `` `RULE_CODE` `` na 1ª coluna; parâmetros como `` `nome`: R$ 1.000 (pf_pf) `` separados por `<br>`) | Ramon | 02:00 (no T04) | todas as regras |
| D6 | Nome do grupo e integrantes no cabeçalho do README | time | 05:30 | T04, T29 |
| D7 | Quem aprova os PRs do Ramon (proposta: a Victoria aprova, o Ramon faz o merge) | Ramon | 01:40 | T01 |
| D8 | `src/schemas/post_pix_transaction.json` é arquivo de contrato? (proposta: sim, só o Ramon altera) | Ramon | 01:30 | T05, T11 |
| D9 | O T15 consulta a view `pix_history` com SQL ou com um model somente leitura | Ramon | 04:15 | T15 |
| D10 | `TASKS.md` e `docs/tarefas/` precisam estar em `develop` para elas lerem e atualizarem o estado | Ramon | 01:25 | todas |
