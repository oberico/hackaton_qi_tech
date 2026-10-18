# [Nome do grupo]

**Integrantes:** [nomes]

## Como o motor de decisão funciona

O motor antifraude de Pix do RNV recebe um Pix em `POST /pix/transaction` e decide `approved`, `two_factor_required` ou `rejected`, sempre com o motivo explicável em `metadata`. A análise é gravada e pode ser consultada depois em `GET /pix/transaction/{id}`. É um serviço único, chamado por outros serviços do RNV (como o de Transferências) com o header `INTERNAL-TOKEN`, nunca pelo cliente final.

### A tese: qual é a dúvida?

Não perguntamos "quão arriscado é este Pix". Perguntamos **qual é a dúvida**, porque a resposta define o que fazer com ele:

| Eixo | Dúvida | O 2FA resolve? | Consequência |
|---|---|---|---|
| **who** (device, canal, rede) | É o cliente mesmo? | Sim | Dúvida só aqui: pedir 2FA |
| **how** (valor, horário, comportamento do pagador) | Isso é normal para ele? | Sim | Dúvida só aqui: pedir 2FA |
| **where** (destino) | O dinheiro vai para golpe ou mula? | **Não** | Um segundo fator do pagador não muda quem recebe |

Por isso o `where` pesa mais: o 2FA confirma quem paga, não quem recebe.

### O fluxo de um POST

1. **Schema (JSON Schema):** valida a forma do payload. Falha vira `400`.
2. **Validação de sentido:** dígito verificador de CPF/CNPJ, `opening_date` não posterior a `transaction_date`, `transaction_date` até 5 minutos no futuro, origem diferente do destino, conta conhecida com outro titular. Falha vira `422` (ou `409` para conta com outro titular).
3. **Insert do Pix:** é a primeira escrita e garante a idempotência. O mesmo `id` com o mesmo payload devolve a análise já feita (`200`); o mesmo `id` com payload diferente é `422 RNV001024`.
4. **Upsert das contas:** a origem usa o nosso participante (`OWN_PARTICIPANT`). ISPB fora da lista do STR não é erro: o participante é criado com `listed = false` e vira o sinal `WHERE_UNKNOWN_PARTICIPANT`.
5. **Montagem do contexto:** os repositories consultam o histórico e montam o `RiskContext`.
6. **Decisão:** `engine.evaluate(context)` devolve o `EngineResult`.
7. **Gravação:** a análise, todas as regras avaliadas (`fired`, `not_fired` ou `unavailable`) e a memória do motor (só se `approved`), em uma transação.
8. **Resposta:** `201 {key, status, metadata}`.

Se o connector externo de IP falhar, o motor decide sem ele e registra isso em `metadata` (`ip_country: "unavailable"`).

### O motor é uma função pura

`evaluate(RiskContext) -> EngineResult` não acessa banco, não chama HTTP, não lê o relógio e não loga. Só o controller o chama. Isso permite testar cada regra e cada célula da matriz montando um `RiskContext` à mão, sem infraestrutura, e versionar a política separada do caminho de I/O.

### Por que a política vive em código e não no banco

Os parâmetros ficam em `src/engine/policy.py`, indexados por fluxo (`pf_pf`, `pf_pj`, `pj_pf`, `pj_pj`), sem número mágico nas regras. Mudar número no banco sem deploy é conveniente, mas obrigaria a versionar o conteúdo para reproduzir decisões antigas. Em código, o git e a `policy_version` fazem isso: toda mudança de parâmetro sobe `POLICY_VERSION`, e cada análise grava a versão e os limiares que usou.

## Regras

Uma linha por regra que existe no código. **Regra** é o `rule_code` entre crases, o mesmo do `metadata`. **Parâmetros** traz os mesmos valores de `src/engine/policy.py`, com unidade em reais e dias (nunca centavos). **Por quê** justifica cada parâmetro: fonte regulatória, quando houver, ou a escolha de design e como foi calibrada.

| Regra | Lógica | Parâmetros | Por quê |
|---|---|---|---|
| `WHO_DEVICE_COMPROMISED` | Eixo `who`, `critical`. Dispara quando o device do Pix já foi usado por **3 ou mais titulares distintos** no total (contados por `account_holder`, ou seja, por documento) **ou** por **2 ou mais titulares distintos nas últimas 24 horas**; basta um dos dois gatilhos. A evidência vem de outra entidade (o device), e não da falta de histórico do pagador; por isso pode rejeitar a 1ª transação do cliente (`critical_axis`). Vale para todos os fluxos. | `DEVICE_COMPROMISED_DOCUMENTS_TOTAL` = 3<br>`DEVICE_COMPROMISED_DOCUMENTS_24H` = 2 | `DEVICE_COMPROMISED_DOCUMENTS_TOTAL`: escolha de design, sem norma por trás. Um aparelho compartilhado por vários titulares é o sinal clássico de aparelho de fraude ou de mula; o corte em 3 deixa de fora o uso legítimo de 2 titulares no mesmo aparelho (por exemplo, um casal), que é comum.<br>`DEVICE_COMPROMISED_DOCUMENTS_24H`: escolha de design. Uma rajada recente de titulares diferentes no mesmo aparelho é mais grave do que o acúmulo ao longo do tempo, por isso o corte é menor (2). A janela de 24h é a mesma do fan-in do destino.<br>É `critical` e não `suspicious` porque é dúvida de quem está usando o aparelho que o 2FA não resolve: o 2FA seria aprovado no próprio aparelho comprometido. Não foi calibrado ainda no simulador. |
| `HOW_NIGHT_LIMIT_EXCEEDED` | Eixo `how`, `suspicious`. Pix PF→PF entre titulares diferentes, feito no período noturno local do pagador, cuja soma (Pix anteriores aprovados ou em 2FA no mesmo período noturno, mais o Pix em análise) fica estritamente acima do limite. Pix às 02h soma desde as 20h do dia anterior. Self-Pix e fluxos PF→PJ, PJ→PF e PJ→PJ ficam de fora. | `NIGHT_START_HOUR` = 20h<br>`NIGHT_END_HOUR` = 6h<br>`NIGHT_LIMIT_MINOR[pf_pf]` = R$ 1.000 | `NIGHT_START_HOUR`, `NIGHT_END_HOUR`: janela noturna do Pix entre pessoas físicas, âncora regulatória do BCB (número da norma não citado: fonte primária ainda não conferida pelo time).<br>`NIGHT_LIMIT_MINOR[pf_pf]`: limite noturno regulatório entre pessoas físicas, o mesmo valor do piso `FLOOR_NIGHT_LIMIT`; estritamente acima, então R$ 1.000,00 exatos passam. Só vale para PF→PF porque o limite trata de pagamento entre pessoas; comércio noturno (PF→PJ) e folha (PJ) são normais, e o self-Pix não é pagamento a terceiro. |
| `HOW_VELOCITY_EXCEEDED` | Eixo `how`. Dispara pelo número de tentativas do pagador nos últimos 10 minutos, **contando todos os status** (`approved`, `two_factor_required` e `rejected`: insistência é sinal). Chegou ao limite `suspicious`, a regra marca `suspicious`; chegou ao limite `critical`, marca `critical`. Os limites são por fluxo: PF paga em poucas tentativas, PJ envia em lote (folha de pagamento). | `VELOCITY_WINDOW_MINUTES` = 10<br>`VELOCITY_10MIN[pf_pf].suspicious` = 3<br>`VELOCITY_10MIN[pf_pf].critical` = 6<br>`VELOCITY_10MIN[pf_pj].suspicious` = 3<br>`VELOCITY_10MIN[pf_pj].critical` = 6<br>`VELOCITY_10MIN[pj_pf].suspicious` = 20<br>`VELOCITY_10MIN[pj_pf].critical` = 40<br>`VELOCITY_10MIN[pj_pj].suspicious` = 20<br>`VELOCITY_10MIN[pj_pj].critical` = 40 | `VELOCITY_WINDOW_MINUTES`: escolha de design; 10 minutos é curto o bastante para pegar rajada e longo o bastante para uma pessoa legítima não chegar ao limite por acaso.<br>`VELOCITY_10MIN` para PF: escolha de design, sem norma por trás. Uma pessoa física raramente faz 3 Pix em 10 minutos, então 3 já pede 2FA (dúvida de comportamento, que o 2FA resolve); 6 é o dobro e indica automação, por isso `critical`.<br>`VELOCITY_10MIN` para PJ: 20 e 40, porque empresa paga em lote (folha de pagamento) e o corte de PF geraria falso positivo; o `critical` é o dobro do `suspicious`, a mesma proporção do PF (decisão D4 do time). Não foi calibrado ainda no simulador. |
| `FLOOR_UNREGISTERED_DEVICE` | Piso regulatório (eixo `floor`, sem nível): pagador PF com device sem histórico (`unknown`) dispara por **dois gatilhos**: (1) valor do Pix acima do limite por transação; ou (2) soma do dia-calendário local do pagador naquele device (Pix anteriores `approved` e `two_factor_required`, mais o Pix em análise) acima do limite diário. Garante no mínimo `two_factor_required` (`regulatory_floor`); sozinho nunca rejeita, a rejeição vinda de outros eixos prevalece, e a confiança não o remove. | `UNKNOWN_DEVICE_TX_LIMIT_MINOR[pf_pf]` = R$ 200<br>`UNKNOWN_DEVICE_TX_LIMIT_MINOR[pf_pj]` = R$ 200<br>`UNKNOWN_DEVICE_DAILY_LIMIT_MINOR[pf_pf]` = R$ 1.000<br>`UNKNOWN_DEVICE_DAILY_LIMIT_MINOR[pf_pj]` = R$ 1.000 | `UNKNOWN_DEVICE_TX_LIMIT_MINOR`: limite por transação para dispositivo não cadastrado, parâmetro regulatório do Pix; estritamente acima, então R$ 200,00 exatos passam.<br>`UNKNOWN_DEVICE_DAILY_LIMIT_MINOR`: limite diário para dispositivo não cadastrado, parâmetro regulatório do Pix; pega o fracionamento em vários Pix pequenos, e o "dia" é o dia-calendário local porque a regra é por dia, não por 24h corridas. Estritamente acima, então R$ 1.000,00 exatos passam.<br>Os dois só valem com pagador PF (PF→PF e PF→PJ). Device `observing` ou `trusted` já tem histórico e não aciona o piso. O número da norma não é citado: a fonte primária ainda não foi conferida pelo time. |
| `FLOOR_NIGHT_LIMIT` | Piso regulatório (eixo `floor`, sem nível): PF→PF entre titulares diferentes, no período noturno local, com soma (incluindo o Pix em análise) estritamente acima do limite. Garante no mínimo `two_factor_required` (`regulatory_floor`); nunca suaviza um `rejected`, e a confiança não o remove. | `NIGHT_START_HOUR` = 20h<br>`NIGHT_END_HOUR` = 6h<br>`NIGHT_LIMIT_MINOR[pf_pf]` = R$ 1.000 | Mesmos parâmetros e mesma fonte de `HOW_NIGHT_LIMIT_EXCEEDED`. A soma conta Pix `approved` e `two_factor_required` (tudo que pode ter saído). A regra do eixo `how` e o piso coexistem: o piso é a garantia regulatória, a regra é o sinal que entra na matriz. |
| `WHERE_DESTINATION_NEW_ACCOUNT` | Eixo `where`, `suspicious`. Dispara quando a conta de destino foi aberta há **menos** de 30 dias na data do Pix (estritamente abaixo: 29 dias dispara, 30 não). Vale para todos os fluxos. | `DESTINATION_NEW_ACCOUNT_DAYS` = 30 dias | `DESTINATION_NEW_ACCOUNT_DAYS`: escolha de design, sem norma por trás. Conta recém-aberta é o destino típico de golpe e de mula, e o 2FA não resolve dúvida de destino (eixo `where`). Os 30 dias são o mesmo corte de "destino jovem" usado em `WHERE_DESTINATION_FAN_IN` e no self-Pix maduro (`MATURE_SELF_PIX_MIN_DESTINATION_AGE_DAYS`), para as regras não se contradizerem. Sozinha só pede 2FA; vira `rejected` quando outro eixo também está suspeito (matriz). |
| `WHERE_UNKNOWN_PARTICIPANT` | Eixo `where`, `suspicious`. Dispara quando o ISPB do participante de destino não está na Relação de participantes do STR carregada no banco (`listed = false`). Não é erro de entrada: o Pix é analisado normalmente e o participante é criado como não listado. Vale para todos os fluxos. | Sem parâmetro numérico. Referência: a lista do STR (BCB, 16/10/2026) | Destino fora da lista oficial é dúvida sobre o destino, que o 2FA não resolve, por isso é sinal e não rejeição direta: um ISPB legítimo recém-criado ou ausente da nossa cópia da lista não pode derrubar o Pix sozinho. Não há limiar a calibrar; o dado vem da tabela de referência `pix_participant`. |
| `WHERE_DESTINATION_FAN_IN` | Eixo `where`, `critical`. Conta de destino aberta há **menos** de 30 dias que recebeu de pelo menos N pagadores distintos nas últimas 24h, contando todas as tentativas (aprovadas, em 2FA e rejeitadas). N depende do fluxo. Destino com 30 dias ou mais fica de fora. Como a evidência vem do destino (outra entidade), pode rejeitar a 1ª transação do pagador. | `FAN_IN_CRITICAL_PAYERS_24H[pf_pf]` = 3<br>`FAN_IN_CRITICAL_PAYERS_24H[pj_pf]` = 3<br>`FAN_IN_CRITICAL_PAYERS_24H[pf_pj]` = 10<br>`FAN_IN_CRITICAL_PAYERS_24H[pj_pj]` = 10<br>`FAN_IN_WINDOW_HOURS` = 24<br>`DESTINATION_NEW_ACCOUNT_DAYS` = 30 | `FAN_IN_CRITICAL_PAYERS_24H`: quando o destino é pessoa física, 3 pagadores distintos em 24h numa conta recém-aberta já é padrão de mula. Quando é pessoa jurídica, o limite sobe para 10 porque loja nova recebe de muitos clientes, mas uma falsa loja recebe de muitos mais. É `critical` porque o 2FA não resolve dúvida de destino. Os valores são escolha de design, sem norma por trás.<br>`FAN_IN_WINDOW_HOURS`: a campanha de golpe aparece nas tentativas recentes, por isso a janela é curta e conta todos os status.<br>`DESTINATION_NEW_ACCOUNT_DAYS`: o mesmo corte de `WHERE_DESTINATION_NEW_ACCOUNT`. |
| `WHERE_DESTINATION_REJECTIONS` | Eixo `where`, `critical`. Destino com rejeições de pelo menos 2 pagadores distintos nas últimas 24h (o mesmo pagador rejeitado várias vezes conta uma vez). Vale para todos os fluxos e para destino de qualquer idade. Como a evidência vem do destino (outra entidade), pode rejeitar a 1ª transação do pagador. | `DESTINATION_REJECTIONS_CRITICAL_PAYERS_24H` = 2<br>`FAN_IN_WINDOW_HOURS` = 24 | `DESTINATION_REJECTIONS_CRITICAL_PAYERS_24H`: é a "fundada suspeita" da Res. BCB 501/2025, como registrado no CLAUDE.md do projeto (texto da norma ainda não conferido pelo time na fonte primária). Duas rejeições de pagadores diferentes tiram a dúvida de que seja um erro isolado de um cliente. Só conta `rejected`, não 2FA.<br>`FAN_IN_WINDOW_HOURS`: a mesma janela de 24h do fan-in. |

## Como as regras viram decisão

Cada regra avaliada marca um dos três eixos (`who`, `how`, `where`) com um nível: `ok`, `suspicious` ou `critical`. O nível final de cada eixo é o mais grave entre suas regras.

### A matriz dos 3 eixos

| Situação | Decisão | `decision_basis` |
|---|---|---|
| Algum eixo `critical` | `rejected` | `critical_axis` |
| 2 ou mais eixos `suspicious` | `rejected` | `two_suspicious_axes` |
| 1 eixo `suspicious` | `two_factor_required` | `single_suspicious_axis` |
| Todos `ok` | `approved` | `clean` |

Dois eixos em dúvida significam que o 2FA, que só resolve a dúvida de um deles, não basta. Os outros valores de `decision_basis` são `regulatory_floor` (decisão imposta por piso regulatório) e `trust_downgrade` (decisão alterada por sinal de confiança).

### Pisos regulatórios

Mínimo `two_factor_required`, independentemente do restante:

- Device sem histórico e valor acima de R$ 200 (`FLOOR_UNREGISTERED_DEVICE`).
- PF→PF noturno (20h às 6h) somando mais de R$ 1.000.

São os únicos números absolutos da política, porque são regulatórios. O resto é relativo: teto do cliente, fluxo e idade das contas. As normas e os valores exatos por regra ficam na tabela de Regras, só com fonte primária conferida.

### Sinais de confiança

Destinatário recorrente, ou Pix para si mesmo (self-Pix) maduro com device confiável, rebaixa **um** eixo `suspicious` para `ok`. Um `critical` nunca é rebaixado. A confiança rebaixa primeiro a dúvida que ela resolve (quem e como), não a de destino, então a ordem é **who → how → where**: com `who` e `where` em `suspicious`, o `who` vira `ok`, o `where` continua `suspicious` e a decisão é `two_factor_required`; só com `where` em `suspicious`, o `where` é rebaixado. O sinal aparece em `trust` (por exemplo `TRUST_RECURRENT_BENEFICIARY`).

### Cold start: ausência de histórico nunca é evidência

- Device novo só é suspeito se o pagador já tem outros devices.
- A primeira transação só é rejeitada por evidência do próprio payload em 2 eixos, ou por histórico de **outra** entidade (device, destino ou IP).
- Cliente sem histórico nunca é rejeitado só por ser novo.

### Fases do pagador

| Fase | Critério | Efeito |
|---|---|---|
| 0 | 0 aprovadas | usa o teto de referência |
| 1 | 1 a 4 aprovadas | mistura teto histórico e de referência |
| 2 | 5+ aprovadas e 30+ dias | predomina o teto histórico |

Teto do cliente = (n · teto_hist + 5 · teto_ref) / (n + 5), onde n é o número de Pix aprovados. O device evolui de `unknown` para `observing` e para `trusted` (1+ aprovada e primeira vez há mais de 24h). Device usado por 3 ou mais documentos é comprometido (`critical`).

### O que conta em cada consulta

| Uso | Status considerados | Por quê |
|---|---|---|
| Somas de limite (noturno, diário de device novo) | `approved` + `two_factor_required` | Conservador: tudo que PODE ter saído |
| Velocity (tentativas) | todos | Insistência é sinal |
| Fan-in do destino (pagadores distintos) | todos | Campanha aparece nas tentativas |
| Rejeições no destino | `rejected` | "Fundada suspeita" (Res. BCB 501/2025) |
| Teto do cliente, device confiável, destinatário recorrente | `approved` | Conservador: só o que CERTAMENTE saiu |

### Racional de custo esperado

É a justificativa teórica da matriz, não um cálculo em runtime (não temos a probabilidade de fraude). Quando a dúvida é de identidade (`who`, `how`), o 2FA resolve e custa pouco, então ele domina a rejeição. Quando a dúvida é do destino (`where`), o 2FA não resolve, então rejeitar domina.

### Exemplo de ponta a ponta

[Marcador: o payload de exemplo do desafio, a decisão `rejected` e o porquê entram na tarefa T18.]

## Como rodar e testar

[Marcador: seção completa na tarefa T17.]
