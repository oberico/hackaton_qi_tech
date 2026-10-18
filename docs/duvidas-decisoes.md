# T08: dúvidas e decisões

Regras WHERE do payload: `WHERE_DESTINATION_NEW_ACCOUNT` e `WHERE_UNKNOWN_PARTICIPANT`. Branch `feat/T08-where-payload-rules`. Para o Ramon conferir na revisão.

## Decisões tomadas

| # | Decisão | Alternativa | Por que esta |
|---|---|---|---|
| 1 | `WHERE_DESTINATION_NEW_ACCOUNT` dispara com idade **estritamente menor** que 30 dias (`< DESTINATION_NEW_ACCOUNT_DAYS`): 29 dias dispara, 30 não | `<=` | O `policy.py` só traz a constante, não diz o sentido da borda. O CLAUDE.md escreve "destino < 30 dias". A borda está testada (`test_exactly_thirty_day_old_destination_does_not_fire`) |
| 2 | `observed` e `threshold` usam as chaves `destination_account_age_days` e `destination_participant_listed` (o mesmo nome do campo do `RiskContext`) | `age_days`, `listed` | A tarefa pede dicts, mas não define as chaves. Reusar o nome do campo evita inventar vocabulário |
| 3 | `WHERE_UNKNOWN_PARTICIPANT`: `threshold = {"destination_participant_listed": true}` | sem `threshold` | `threshold` é o valor esperado para a regra não disparar, o mesmo papel dos outros `threshold` |
| 4 | As duas regras são `suspicious`, nunca `critical` | `critical` para ISPB fora da lista | O CLAUDE.md diz que ISPB fora da lista "não é erro" e vira sinal. Sozinha só pede 2FA; vira `rejected` quando outro eixo também está suspeito |
| 5 | A descrição cita "lista de participantes do STR do BCB" sem número de norma | citar resolução | Regra do projeto: só número de norma com a fonte primária aberta |
| 6 | O README justifica `WHERE_UNKNOWN_PARTICIPANT` com argumento de design: um ISPB legítimo ausente da nossa cópia da lista não deve derrubar o Pix sozinho | omitir o "por quê" | O CLAUDE.md pede o porquê de cada parâmetro. **Esta frase é minha, não vem do CLAUDE.md. Peço leitura** |
| 7 | O README justifica os 30 dias como o mesmo corte de "destino jovem" do fan-in e do self-Pix maduro | justificar com dado | Vem do CLAUDE.md (linha do self-Pix maduro, "D1"). Não há calibração por simulador ainda, porque o farm é a T23 |

## Dúvidas e como foram resolvidas

1. **Faltava o parâmetro da idade do destino no `policy.py`.** Só existia `MATURE_SELF_PIX_MIN_DESTINATION_AGE_DAYS`, que pertence à regra de confiança. Usá-lo emprestado acoplaria duas regras que podem mudar separadamente. Avisei o Ramon, ele criou `DESTINATION_NEW_ACCOUNT_DAYS = 30` e eu usei o nome dele.
2. **O `test_cold_start.py` quebrou** quando a regra real passou a disparar. O contexto `challenge_payload_context` usava destino de 7 dias e esperava `single_suspicious_axis`, o que só era verdade com o eixo `where` vazio. O arquivo é da T03 e não estava na minha lista, então parei e avisei. O Ramon parametrizou a idade do destino (padrão 400) e eu fiz rebase.

## Ciclos TDD: o que foi vermelho de verdade

| Ciclo | Tipo | Prova de que o teste testa algo |
|---|---|---|
| `WHERE_UNKNOWN_PARTICIPANT` | red real | 3 falhas: `WHERE_UNKNOWN_PARTICIPANT was not evaluated` e `OK == SUSPICIOUS` |
| `WHERE_DESTINATION_NEW_ACCOUNT` (7 dias) | red real | 2 falhas, mesmo motivo |
| Borda de 29/30 dias | caracterização (passou de primeira) | Mutação `<` → `<=` derrubou o teste dos 30 dias exatos; código restaurado |
| Matriz | caracterização (passou de primeira) | Tirar `destination_new_account` do `RULES` derrubou 3 dos 4 testes; código restaurado |

Na primeira versão do red, dois testes falhavam com `StopIteration` (erro de infraestrutura, não de assertion). Troquei o helper `rule_of` por uma assertion legível antes de commitar o red.

## O que ficou de fora

- Cálculo da idade do destino a partir do `opening_date` e do `transaction_date`: é a T10 (montagem do `RiskContext`).
- Remover o `xfail` da T13: é da T10, quando o motor real entrar no controller.
- Calibração dos 30 dias contra o simulador: é a T23.
- `tests/unit/test_readme_rules.py` ainda não existe (T19). As duas linhas novas do README precisarão passar por ele.

# T14: dúvidas e decisões

Regras WHERE de histórico: `WHERE_DESTINATION_FAN_IN` e `WHERE_DESTINATION_REJECTIONS`. Branch `feat/T14-where-history-rules`. Para o Ramon conferir na revisão.

## Decisões tomadas

| # | Decisão | Alternativa | Por que esta |
|---|---|---|---|
| 1 | Os testes entram como linhas nas tabelas de `test_numeric_borders.py` (`FAN_IN_BORDERS`, `REJECTIONS_BORDERS`) e de `test_matrix.py` (`CRITICAL_WHERE_CELLS`), sem arquivos novos | `test_where_destination_*.py` | O refactor das 05:00 acabou com `tests/unit/` e o Ramon confirmou no grupo |
| 2 | A idade do destino (`< 30`) do fan-in usa `DESTINATION_NEW_ACCOUNT_DAYS` | `MATURE_SELF_PIX_MIN_DESTINATION_AGE_DAYS` | Confirmado pelo Ramon. As duas regras de "destino jovem" devem mudar juntas |
| 3 | Fan-in: `observed = {distinct_payers_24h, destination_account_age_days}` e `threshold = {distinct_payers_24h: N do fluxo, destination_account_age_days: 30}` | só `distinct_payers_24h` | A regra tem duas condições (pagadores e idade); expor as duas deixa o motivo explicável no `metadata` |
| 4 | Rejeições: `observed`/`threshold` com a chave `rejections_from_distinct_payers_24h` (o nome do campo do `RiskContext`) | `rejections` | A tarefa pede dicts mas não define as chaves. Mesmo critério da T08 |
| 5 | Limites com `>=` (3 pagadores dispara, 2 não; 2 rejeições disparam, 1 não) | `>` | O texto da tarefa diz "N ou mais" / "2+", e as bordas estão em tabela |
| 6 | Os dois `observed` aparecem também quando a regra não dispara (`not_fired` com `observed`/`threshold`) | `None` | Mesmo padrão das regras da T08 |
| 7 | Fan-in de destino novo dispara também `WHERE_DESTINATION_NEW_ACCOUNT` (suspicious); o eixo fica `critical` pelo maior nível | suprimir a regra mais fraca | As regras são independentes e todas ficam registradas no `metadata`. Teste: `fan_in_on_new_destination` |
| 8 | README: o "por quê" do fan-in repete o CLAUDE.md (loja nova × falsa loja) e acrescenta que 3 pagadores distintos em conta recém-aberta é padrão de mula para destino PF | só a frase do CLAUDE.md | **A parte "padrão de mula" e a frase de que duas rejeições afastam o erro isolado são minhas. Peço leitura** |
| 9 | README cita a Res. BCB 501/2025 só como registrado no CLAUDE.md, avisando que a fonte primária ainda não foi conferida | citar sem ressalva | Regra do projeto: número de norma só com a fonte primária aberta |

## Dúvidas e como foram resolvidas

1. **Arquivos de teste:** a lista da T14 e o "padrão desde as 05:00" divergiam. O Ramon respondeu: tocar `test_numeric_borders.py` e `test_matrix.py` e não criar os arquivos novos.
2. **Constante da idade do destino:** confirmada como `DESTINATION_NEW_ACCOUNT_DAYS`.

## Ciclos TDD: o que foi vermelho de verdade

| Ciclo | Tipo | Prova |
|---|---|---|
| 1. Fan-in pf_pf (2 → ok, 3 → critical) | red real | 2 falhas: `WHERE_DESTINATION_FAN_IN was not evaluated exactly once` |
| 2. Fan-in nos outros fluxos | caracterização | Mutação "ignorar o fluxo" derrubou 4 linhas (pf_pj e pj_pj) |
| 3. Destino com 30+ dias | caracterização | Mutação "ignorar a idade do destino" derrubou 2 linhas |
| 4. Rejeições (1 → ok, 2 → critical) | red real | 4 falhas: `WHERE_DESTINATION_REJECTIONS was not evaluated exactly once` |
| 5. Matriz: crítico sozinho → `rejected` (`critical_axis`) na 1ª transação | caracterização | Mutação "tirar a regra de rejeições" derrubou 2 testes |

No ciclo 1, a primeira versão do teste esperava `approved` abaixo do limite de fan-in, mas o destino de 7 dias também dispara `WHERE_DESTINATION_NEW_ACCOUNT`, então o certo é `two_factor_required`. Corrigi o teste no próprio commit do red (branch ainda local) e refiz o red e o green. A saída do red e do green que vale é a da versão corrigida.

## O que ficou de fora

- As contagens `distinct_payers_24h` e `rejections_from_distinct_payers_24h` vêm do `RiskContext`; as consultas são da T15. Não verifiquei se a contagem inclui o pagador do Pix em análise, e por isso o README não afirma isso.
- Teste por HTTP dessas regras: entra quando o motor real estiver no controller (T10/T15).
- Calibração dos limites (3 e 10 pagadores) no simulador: T23.
