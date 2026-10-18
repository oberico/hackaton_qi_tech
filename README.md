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
| `HOW_ABOVE_CUSTOMER_CEILING` | Eixo `how`, `suspicious`. Dispara quando o valor do Pix fica estritamente acima do **teto do cliente**. O teto mistura o histórico do pagador com um teto de referência: `teto = (n × teto_hist + K × teto_ref) / (n + K)`, com `n` = Pix aprovados do pagador nos últimos 90 dias e `K` = peso do teto de referência. `teto_hist` = `HISTORY_MARGIN` × percentil 95 (interpolação linear entre os valores ordenados) dos valores aprovados. `teto_ref` depende do pagador: PF com conta de origem aberta há menos de 90 dias, PF com 90 dias ou mais, ou PJ. Sem Pix aprovado (fase 0 do pagador), `n` = 0 e vale só o `teto_ref`: a ausência de histórico nunca é evidência, então a 1ª transação só dispara se passar do teto de referência. Conforme `n` cresce o teto passa a seguir o comportamento do próprio cliente (fases 1 e 2). O teto é truncado para centavos inteiros. Vale para todos os fluxos. | `REFERENCE_CEILING_NEW_ACCOUNT_DAYS` = 90 dias<br>`REFERENCE_CEILING_MINOR.individual_new_account` = R$ 1.000<br>`REFERENCE_CEILING_MINOR.individual` = R$ 3.000<br>`REFERENCE_CEILING_MINOR.company` = R$ 20.000<br>`HISTORY_WINDOW_DAYS` = 90 dias<br>`HISTORY_PERCENTILE` = 0,95<br>`HISTORY_MARGIN` = 1,5<br>`SHRINKAGE_K` = 5 | `REFERENCE_CEILING_MINOR`: escolha de design, sem norma por trás (o R$ 1.000 não vem de resolução do BCB). É um ponto de partida conservador para quem ainda não tem histórico: conta de PF com menos de 90 dias tem teto menor porque a conta nova é o perfil de conta de passagem; PF com 90 dias ou mais tem R$ 3.000, acima do Pix de R$ 1.500 do payload do desafio, para a 1ª transação de um cliente comum não ser tocada; PJ tem R$ 20.000 porque pagamentos de empresa são maiores por natureza. Não foi calibrado ainda no simulador.<br>`REFERENCE_CEILING_NEW_ACCOUNT_DAYS`: escolha de design; 90 dias é a janela de histórico da política, então uma conta que já completou a janela é tratada como estabelecida.<br>`HISTORY_WINDOW_DAYS`: 90 dias é o limite de consulta no caminho síncrono (índice + intervalo de data), e cobre ciclos mensais de gasto.<br>`HISTORY_PERCENTILE`: o p95 ignora o valor atípico raro do próprio cliente sem deixar o teto subir até o maior Pix já feito.<br>`HISTORY_MARGIN`: 1,5 dá folga de 50% sobre o p95 para que variação normal de gasto não dispare; escolha de design, sem calibração ainda.<br>`SHRINKAGE_K`: 5 equivale a dizer que o teto de referência pesa como 5 Pix aprovados; com poucos Pix o teto ainda é quase o de referência, com 5 aprovados já pesa meio a meio e depois o histórico passa a dominar. É o mesmo 5 que define a fase 2 do pagador (5 aprovados e 30 dias). Dúvida de comportamento (`how`) que o 2FA resolve, por isso `suspicious` e nunca `critical`. |
| `HOW_EARLY_MORNING_AMOUNT` | Eixo `how`, `suspicious`. Dispara quando o Pix é feito de madrugada no horário local do pagador (00:00 a 05:59, a hora local vem de `transaction_date` + `utc_offset_minutes`) e o valor está **estritamente acima** do mínimo e **até** o máximo da faixa (R$ 200,00 exatos não disparam; R$ 1.000,00 exatos disparam). Acima do máximo a regra não atua: PF→PF entre titulares diferentes já cai no limite noturno (`HOW_NIGHT_LIMIT_EXCEEDED`). Vale para todos os fluxos e não depende de histórico do pagador (o sinal está no próprio Pix). | `EARLY_MORNING_START_HOUR` = 0h<br>`EARLY_MORNING_END_HOUR` = 6h<br>`EARLY_MORNING_MIN_AMOUNT_MINOR` = R$ 200<br>`EARLY_MORNING_MAX_AMOUNT_MINOR` = R$ 1.000 | `EARLY_MORNING_START_HOUR`, `EARLY_MORNING_END_HOUR`: escolha de design, sem norma por trás; madrugada é a faixa em que o uso legítimo é raro, então um valor médio ali foge do padrão da maioria dos clientes (hipótese, ainda não medida no simulador); a janela é mais curta que a janela noturna regulatória (20h às 6h) de propósito, para o sinal ser mais específico.<br>`EARLY_MORNING_MIN_AMOUNT_MINOR`: escolha de design; abaixo de R$ 200 o dano é pequeno e o valor é comum em madrugada (táxi, lanche). Usa o mesmo número do limite de dispositivo não cadastrado só por coerência de ordem de grandeza, e tem parâmetro próprio para poder ser calibrado sozinho.<br>`EARLY_MORNING_MAX_AMOUNT_MINOR`: escolha de design; R$ 1.000 é o limite noturno regulatório entre pessoas físicas, então acima disso o sinal já existe em outra regra e o piso regulatório cobre. É dúvida de comportamento (`how`) que o 2FA resolve, por isso `suspicious`. Não foi calibrado ainda no simulador. |
| `WHO_DEVICE_UNKNOWN` | Eixo `who`, `suspicious`. Dispara quando o device do Pix não tem nenhum Pix aprovado do pagador (estado `unknown`) **e** o pagador já tem pelo menos um outro device com Pix aprovado. Pagador sem nenhum device conhecido (1ª transação, ou só histórico sem aprovação) não dispara: ausência de histórico nunca é evidência, então o 1º device de um cliente não vira dúvida. O estado do device é `unknown` (sem aprovado), `observing` (aprovado, mas o primeiro aprovado tem 24h ou menos) ou `trusted` (aprovado há mais de 24h); só `unknown` dispara. É uma regra de sinal, independente do piso `FLOOR_UNREGISTERED_DEVICE`: o piso garante o 2FA por valor, esta regra entra na matriz e, somada a outro eixo suspeito, rejeita. Vale para todos os fluxos. | `DEVICE_UNKNOWN_MIN_KNOWN_DEVICES` = 1<br>`DEVICE_TRUSTED_AFTER_HOURS` = 24h | `DEVICE_UNKNOWN_MIN_KNOWN_DEVICES`: escolha de design. Um cliente que sempre usou outro aparelho e aparece num aparelho novo é dúvida de identidade (`who`), que o 2FA resolve; com 0 devices conhecidos não há contra o que comparar, por isso o mínimo é 1 e a 1ª transação fica `ok`.<br>`DEVICE_TRUSTED_AFTER_HOURS`: escolha de design; um device aprovado há mais de 24h deixa de ser novo, e a espera impede que um fraudador ganhe confiança com um único Pix aprovado e use o device logo em seguida. Não foi calibrado ainda no simulador. |
| `HOW_RETRY_AFTER_REJECTION` | Eixo `how`, `suspicious`. É a "sondagem": o pagador teve um Pix `rejected` e, em **menos de** 10 minutos, tenta de novo com valor **estritamente menor** que o rejeitado. A rejeição considerada é a mais recente do mesmo pagador (conta de origem) nos últimos 90 dias. Valor igual ou maior, ou nova tentativa com 10 minutos ou mais, não dispara. Sem rejeição anterior a regra não atua (sem histórico, nunca é evidência). Vale para todos os fluxos. | `RETRY_AFTER_REJECTION_WINDOW_MINUTES` = 10 | `RETRY_AFTER_REJECTION_WINDOW_MINUTES`: escolha de design, sem norma por trás; é o mesmo horizonte de 10 minutos da velocity (`VELOCITY_WINDOW_MINUTES`), curto o bastante para ligar a nova tentativa à rejeição sem pegar um cliente que desistiu e voltou depois. Reduzir o valor depois de uma rejeição é o comportamento de quem testa o limite do antifraude; a rejeição do motor é o rótulo aproximado de fraude que temos (não há confirmação externa), por isso o sinal é `suspicious` e não `critical`: dúvida de comportamento, que o 2FA resolve. Não foi calibrado ainda no simulador. |
| `HOW_TEST_PIX` | Eixo `how`, `suspicious`. É o "Pix de teste": o pagador mandou, nos últimos 15 minutos, um Pix de até R$ 10 (qualquer status) ao **mesmo destino**, e agora manda um Pix de pelo menos R$ 200 e de pelo menos 20 vezes o valor do teste a esse destino. Não dispara se o destino já era conhecido antes do teste, isto é, se existe Pix aprovado do pagador a esse destino anterior à janela de 15 minutos (o próprio Pix de teste, quando aprovado, não cria essa relação). O histórico (Pix pequeno no destino, já com o fator de 20 vezes aplicado ao valor atual) é calculado na consulta do resumo do pagador; o motor combina com o valor mínimo e com a relação anterior com o destino. Com os valores atuais, 20 vezes o teto de R$ 10 é exatamente o mínimo de R$ 200. Vale para todos os fluxos. | `TEST_PIX_MAX_AMOUNT_MINOR` = R$ 10<br>`TEST_PIX_WINDOW_MINUTES` = 15<br>`TEST_PIX_FOLLOWUP_MIN_AMOUNT_MINOR` = R$ 200<br>`TEST_PIX_FOLLOWUP_MULTIPLIER` = 20 | `TEST_PIX_MAX_AMOUNT_MINOR`: escolha de design, sem norma por trás; golpista que testa se a conta recebe e se o dono não percebe costuma mandar valor simbólico, e R$ 10 deixa de fora Pix pequenos legítimos acima disso.<br>`TEST_PIX_WINDOW_MINUTES`: escolha de design; o teste e o Pix grande vêm juntos, e 15 minutos cobre o intervalo de quem espera a confirmação antes de mandar o valor real.<br>`TEST_PIX_FOLLOWUP_MIN_AMOUNT_MINOR`: escolha de design; abaixo de R$ 200 o Pix seguinte não compensa a investigação e coincide com a ordem de grandeza do piso de device não cadastrado.<br>`TEST_PIX_FOLLOWUP_MULTIPLIER`: escolha de design; exigir um salto de 20 vezes separa o teste real do cliente que paga duas contas pequenas ao mesmo destino. É dúvida de comportamento (`how`) que o 2FA resolve, por isso `suspicious`. Não foi calibrado ainda no simulador. |

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
