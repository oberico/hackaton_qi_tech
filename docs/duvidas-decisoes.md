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
