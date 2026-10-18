# Modelo de dados — decisões

## Origem
Três propostas avaliadas: (A) uma tabela desnormalizada + análises + hits; (B) contas normalizadas + parâmetros de regra no banco + memória completa; (C) registro imutável + perfis como cache recalculável + política versionada. O modelo final pega a **filosofia de C**, a **normalização de contas de B** e a **simplicidade de A** onde ela basta.

## Tabelas
| Grupo | Tabela | Papel |
|---|---|---|
| Domínio | `pix_participant` | ISPBs válidos (lista oficial do BCB) |
| Domínio | `person_type`, `analysis_status`, `risk_level`, `rule_axis`, `rule_outcome` | enumeradores em tabela de lookup (nunca texto solto nem ENUM nativo) |
| Registro | `account` | conta única por (participante, agência, conta); titular e abertura |
| Registro | `pix_transaction` | o Pix como chegou, normalizado + payload cru |
| Registro | `pix_analysis` | a decisão (1:1), níveis por eixo (FK para `risk_level`), `decision_basis`, retrato dos sinais |
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
