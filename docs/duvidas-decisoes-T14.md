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
