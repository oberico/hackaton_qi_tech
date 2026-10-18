# Modelo de dados — decisões

## Origem
Três propostas avaliadas: (A) uma tabela desnormalizada + análises + hits; (B) contas normalizadas + parâmetros de regra no banco + memória completa; (C) registro imutável + perfis como cache recalculável + política versionada. O modelo final pega a **filosofia de C**, a **normalização de contas de B** e a **simplicidade de A** onde ela basta.

## Tabelas
| Grupo | Tabela | Papel |
|---|---|---|
| Domínio | `pix_participant` | ISPBs válidos (lista oficial do BCB) |
| Domínio | `person_type`, `analysis_status`, `decision_basis`, `risk_level`, `rule_axis`, `rule_outcome` | enumeradores em tabela de lookup (nunca texto solto nem ENUM nativo) |
| Registro | `account_holder` | o titular: documento (único) e PF/PJ |
| Registro | `account` | conta única por (participante, agência, número), com a abertura; aponta para o titular |
| Registro | `pix_transaction` | o Pix como chegou, normalizado + payload cru |
| Registro | `pix_analysis` | a decisão (1:1): status, `decision_basis`, versão da política, retrato dos sinais |
| Registro | `pix_analysis_axis` | o nível de cada eixo (who/how/where) da análise, uma linha por eixo |
| Registro | `pix_analysis_rule` | cada regra avaliada, inclusive as que não dispararam ou não tinham dado |
| Memória | `account_device` | aparelhos com Pix aprovado (nosso "dispositivo cadastrado") |
| Memória | `account_counterparty` | destinos com Pix aprovado (recorrência) |
| Visão | `pix_history` | transação + status para as consultas de janela |

## Decisões para defender
- **Conta normalizada (e não desnormalizada na transação):** a mesma conta aparece como pagadora e recebedora; normalizar permite fan-in por conta, detectar conta que muda de titular (409) e chave estrangeira de verdade nos vínculos.
- **Transação separada da análise:** o Pix é o fato; a análise é a opinião do motor com uma política. Separadas, dá para reavaliar com outra política sem tocar no fato.
- **Sem `response` gravada:** POST repetido e GET reconstroem a resposta pelo DTO da análise, que é imutável (mesma convenção do RNV: nada de `response_body`).
- **`pix_analysis_rule` com `not_fired` e `unavailable`:** "não sabia se o aparelho era conhecido" é diferente de "sabia e era novo".
- **`utc_offset_minutes`:** o `TIMESTAMPTZ` guarda o instante e descarta o fuso; sem o offset não há como saber se era madrugada para o cliente. A hora local é derivada (`transaction_date + offset`).
- **Centavos em `BIGINT` com sufixo `_minor`** (`amount_minor`): sem float, sem arredondamento.
- **Memória só com `approved`:** rejeitado não ensina o motor (senão o golpista infla a média tentando). Somas de limite, ao contrário, contam approved + 2FA (o que pode ter saído).

## Descartado
- **Parâmetros de regra no banco (`rule_parameters`):** mudar número sem deploy é bom em produção, mas exige versionar o conteúdo para reproduzir decisões. Aqui a política vive em código (`src/engine/policy.py`), versionada pelo git e pela `policy_version`, e os limiares usados ficam gravados em cada `pix_analysis_rule`.
- **Perfil agregado por conta (`account_profile`, Welford, p95):** na nossa escala a consulta indexada responde em milissegundos; um cache exigiria sincronização e teste de recálculo. Em produção, viraria cache recalculável a partir do registro.
- **Redis:** mais um serviço, consistência entre cache e banco, e nenhum ganho mensurável no volume do desafio. Índices compostos `(entidade, transaction_date DESC)` resolvem.
- **`invalid_requests`:** gravar no caminho de erro exige escrita fora da transação que falhou; o log estruturado do Base Service já registra o 400/422.
- **Marcação de risco persistida (`risk_flags`) e sinais externos:** "destino suspeito" é derivado de consulta (rejeições recentes), sem estado extra para manter.

## Revisão do tech lead (18/10, 02h) e o que mudou
- **Identificador forte e caminho de acesso:** com 120 milhões de contas, uma consulta sem índice varre a tabela inteira e o Pix que sairia em 2 s sai em 1,5 min. Toda consulta do caminho síncrono agora tem índice declarado e conferido com `EXPLAIN` (tabela abaixo).
- **`BIGINT` nas tabelas que crescem:** `SERIAL` é `INTEGER` (2,1 bilhões); `pix_analysis_rule` cresce ~15 linhas por Pix. Tabelas de volume e as FKs para elas viraram `BIGSERIAL`/`BIGINT`.
- **Nada de regra de negócio no `id` serial:** ele tem buracos e aceita insert manual. Ordem por `transaction_date`, identidade pela chave natural ou pela chave pública UUID.
- **Titular separado da conta (`account_holder`):** documento e PF/PJ descrevem a pessoa, não a conta. Uma pessoa com várias contas aparece uma vez; "device usado por N pessoas" conta titulares, não contas.
- **Nível por eixo em tabela filha (`pix_analysis_axis`):** três colunas `who_level_id`/`how_level_id`/`where_level_id` apontando para a mesma tabela liam como se existissem tabelas `who`, `how` e `where`. Agora é uma linha por eixo, com o mesmo `rule_axis` usado em `pix_analysis_rule`.
- **`decision_basis` virou lookup**, como os outros enumeradores.
- **Constraints com nome** (`uq_*`), para o erro de violação dizer qual regra quebrou.
- **Chave pública em `UUID` nativo, não `CHAR(36)`:** `analysis_key` é `UUID DEFAULT gen_random_uuid()` (v4). Medido com 1 milhão de análises: índice de 39 MB contra 56 MB em `CHAR(36)`, e comparação binária em vez de collation. O UUID **não** vira PK nem FK: o v4 é aleatório, então cada insert cai numa página qualquer do B-tree (page split, cache frio); a PK `BIGSERIAL` insere sempre no fim. Por isso a PK continua `BIGINT` (8 bytes nas FKs) e o UUID é só o identificador exposto.
- **Índices de janela *covering* (`INCLUDE`):** cada índice `(entidade, transaction_date DESC)` carrega as colunas que a consulta lê (`amount_minor`, `destination_account_id`, `device_id`, `channel` na origem; `source_account_id` em destino, device e IP). Resultado: Index Only Scan, `Heap Fetches: 0`.
- **Removido `idx_pix_analysis_status`:** três valores possíveis, nenhum plano usa (o status é lido pela análise de um Pix, via `uq_pix_analysis_pix_transaction`), e custaria escrita em todo insert.

## Caminho de acesso (conferido com `EXPLAIN ANALYZE`, Postgres 16, 1 milhão de Pix, 60 mil contas)
| Consulta | Chave | Índice | Plano medido |
|---|---|---|---|
| Participante pelo ISPB | `ispb` | `uq_pix_participant_ispb` | Index Scan |
| Titular pelo documento | `document_number` | `uq_account_holder_document_number` | Index Scan |
| Conta pela chave natural | participante + agência + número | `uq_account_participant_branch_number` | Index Scan, 0,01 ms |
| Idempotência / GET | `transaction_id` | `uq_pix_transaction_transaction_id` | Index Scan, 0,04 ms com a análise |
| Análise do Pix | `pix_transaction_id` | `uq_pix_analysis_pix_transaction` | Index Scan |
| Eixos e regras da análise | `pix_analysis_id` | `uq_pix_analysis_axis`, `uq_pix_analysis_rule` | Index Scan |
| Análise pelo id interno (leitura logo após gravar, com status e base da decisão) | `pix_analysis.id` | `pix_analysis_pkey` + `analysis_status_pkey` + `decision_basis_pkey` | Index Scan, 0,09 ms; lookups de 3 a 6 linhas |
| Gravação das regras avaliadas (INSERT em `pix_analysis_rule`, ids de eixo, resultado e nível por subconsulta de enumerador) | `enumerator` nos lookups | `rule_axis_enumerator_key`, `rule_outcome_enumerator_key`, `risk_level_enumerator_key` | 3 Index Scans de 1 linha (0,004 a 0,007 ms cada); INSERT total 0,5 ms com as 4 FKs |
| Velocity, somas e teto do pagador | conta de origem + janela | `idx_pix_transaction_source_date` INCLUDE (`amount_minor`, `destination_account_id`, `device_id`, `channel`) | Index Only Scan, 0 heap, 0,05 ms |
| Fan-in do destino | conta de destino + janela | `idx_pix_transaction_destination_date` INCLUDE (`source_account_id`) | Index Only Scan, 0 heap, 0,04 ms |
| Rejeições no destino | conta de destino + janela, status da análise | `idx_pix_transaction_destination_date` + `uq_pix_analysis_pix_transaction` | Nested Loop de Index Scans, 0,04 ms |
| Device compartilhado (titulares distintos) | `device_id` + janela | `idx_pix_transaction_device_date` INCLUDE (`source_account_id`) + `account_pkey` | Index Only Scan + Index Scan, 0,06 ms |
| IP compartilhado | `ip_address` + janela | `idx_pix_transaction_ip_date` INCLUDE (`source_account_id`) | Index Only Scan, 0 heap, 0,02 ms |
| Device conhecido e devices do pagador (T20, `AccountDeviceRepository.known_devices`: `first_approved_at` do device e `count(*)` dos devices da conta com `first_approved_at < t`, uma consulta com `FILTER`) | conta de origem (+ `device_id` no `FILTER`) | `uq_account_device` (prefixo `account_id`) | Index Scan, 0,05 ms, 5 buffers (1 linha por device aprovado da conta) |
| Destinatário recorrente (T20, `AccountCounterpartyRepository.find_relationship`: `approved_count` e `first_approved_at` do par, `first_approved_at < t`) | origem + destino | `uq_account_counterparty` | Index Scan de 1 linha, 0,03 ms, 2 buffers |
| Contas do mesmo titular | `account_holder_id` | `idx_account_holder` | Index Scan |
| Última rejeição do pagador e seu valor (`payer_summary`, `last_rejection_at` e `rejected_amounts_latest_first`: `MAX(transaction_date)` e `array_agg(amount_minor ORDER BY transaction_date DESC)` com `FILTER (status = rejected)`, mesma consulta do resumo, sem ida extra ao banco) | conta de origem + `transaction_date` em [t − 90d, t) | `idx_pix_transaction_source_date` + `uq_pix_analysis_pix_transaction` | Bitmap Index Scan + Index Scan por linha, 0,6 a 1,6 ms (58 a 68 linhas, 600 mil Pix e 3 mil contas); sem Seq Scan em `pix_transaction` |
| Pix de teste (`payer_summary`, `test_pix_count`: `COUNT(*) FILTER` por destino, janela de 15 min, valor ≤ R$ 10 e 20 × valor ≤ valor atual) | conta de origem + `transaction_date` em [t − 90d, t) | `idx_pix_transaction_source_date` (destino no INCLUDE) | Mesmo plano da linha anterior: agregado extra da mesma consulta, 0,6 ms |
| Resumo do pagador no T15 (`payer_summary`: velocity, soma diária do device, approved, 1º approved, valores approved 90d; uma consulta com `FILTER`. Desde o T20, device confiável, devices conhecidos e relação com o beneficiário saem da memória, linhas acima) | conta de origem + `transaction_date` em [t − 90d, t) | `idx_pix_transaction_source_date` + `uq_pix_analysis_pix_transaction` (status) | Index Scan + Index Scan por linha, 0,63 ms (17 linhas); Index Scan e não Index Only porque o join com a análise precisa de `pix_transaction.id`, fora do INCLUDE |
| Soma noturna PF→PF para titulares diferentes (`sum_night_amount_to_individuals`, só no período noturno) | conta de origem + [início da noite local, t) | `idx_pix_transaction_source_date` + `uq_pix_analysis_pix_transaction` + `account_pkey` + `account_holder_pkey` | Nested Loop de Index Scans, 0,05 ms |
| Titulares distintos no device, 90d e 24h (`count_device_holders`) | `device_id` + [t − 90d, t) | `idx_pix_transaction_device_date` + `account_pkey` | Index Only Scan (Heap Fetches: 0) + Index Scan, 0,24 ms |
| Pagadores distintos e rejeições de outros pagadores no destino, 24h (`count_other_payers_to_destination`) | conta de destino + [t − 24h, t) | `idx_pix_transaction_destination_date` + `uq_pix_analysis_pix_transaction` | Index Scan + Index Scan, 0,08 ms |
| Pagadores distintos no IP, 1h (`count_other_payers_from_ip`) | `ip_address` + [t − 1h, t) | `idx_pix_transaction_ip_date` | Index Only Scan (Heap Fetches: 0), 0,09 ms |
| Memória do device após Pix `approved` (T20, `AccountDeviceRepository.record_approval`: `INSERT ... ON CONFLICT (uq_account_device) DO UPDATE SET approved_count = approved_count + 1`, `first_approved_at = LEAST`, `last_approved_at = GREATEST`, com o `transaction_date` do Pix) | conta de origem + `device_id` | `uq_account_device` (Conflict Arbiter) | Insert com Conflict Resolution UPDATE, 0,36 ms (base de teste, 58 linhas); sem lock explícito, o arbiter serializa só a linha do par |
| Memória do par origem → destino após Pix `approved` (T20, `AccountCounterpartyRepository.record_approval`: idem, mais `approved_amount_minor = approved_amount_minor + amount`) | conta de origem + conta de destino | `uq_account_counterparty` (Conflict Arbiter) | Insert com Conflict Resolution UPDATE, 0,11 ms (base de teste, 73 linhas) |

Repository novo entra nesta tabela no mesmo PR. Para conferir: `EXPLAIN (ANALYZE, BUFFERS)` da consulta com um id real; o plano precisa mostrar o índice da linha, sem `Seq Scan` em `pix_transaction`, `pix_analysis`, `account` ou `account_holder`.
