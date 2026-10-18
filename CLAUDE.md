# CLAUDE.md

Motor antifraude de Pix do RNV — final (hackathon) do Bootcamp QI Tech 2026, área Risk Solutions. API que recebe um Pix (`POST /pix/transaction`), decide `approved`, `two_factor_required` ou `rejected` com motivo explicável em `metadata`, grava tudo e devolve a análise em `GET /pix/transaction/{id}`. Serviço único, chamado por outros serviços (como o Transferências do RNV), nunca pelo cliente final. Entrega: domingo 18/10 até 12:00 (code freeze 08:00).

O payload de exemplo do desafio está em `tests/fixtures/challenge_example_payload.json` (resultado esperado: `rejected`). Antes de codar, leia a seção "Entrega" abaixo, `docs/modelo-de-dados.md` (o porquê de cada tabela e o que foi descartado), `docs/catalogo-de-erros.md` (os códigos) e `src/engine/risk_context.py` (o contrato do motor). Em conflito, este arquivo vence e você me avisa. Em caso de dúvida, me pergunte. Não faça suposições sobre regra de negócio.

**Herança:** a infraestrutura vem do serviço `banco/` do repositório `oberico/desafio_qitech` (já evoluído a partir do Base Service): `errors/` (base_error, handlers com os 400 granulares RNV000007–012), `utils/` (`schema_handler`, `cpf`, `cnpj`, `payload_hash`, `logger`, `request_context`), `middlewares/`, `tests/utils/` (harness) e o workflow de CI. Copie de lá, não do Base Service cru. `sample_entity` e o domínio do banco não entram.

**Método: TDD.** Toda fatia começa pelo teste: escreve, vê falhar (red), implementa o mínimo (green), refatora com a rede verde.

## Entrega: a API + o README.md (não há RFC nem documento extra)

Os entregáveis são três: o código, o **README.md** e a apresentação (7 min + 3 min). **A correção começa pelo README**: a banca lê as regras descritas e o porquê de cada parâmetro, depois roda o projeto seguindo o README e confere se as decisões batem com o que está escrito. Os arquivos em `docs/` são apoio interno do time e dos agentes; a banca pode não abrir nenhum. **Tudo que precisa ser avaliado tem que estar no README.**

O README segue **exatamente** o modelo do desafio, nesta ordem e com estes títulos:

```
# [Nome do grupo]
**Integrantes:** [nomes]

## Como o motor de decisão funciona
## Regras
| Regra | Lógica | Parâmetros | Por quê |
## Como as regras viram decisão
## Como rodar e testar
```

Depois dessas seções (nunca antes, nunca no lugar delas) podem vir: `## Modelo de dados`, `## Opções descartadas`, `## Limitações conhecidas`, `## Contrato da API`.

Regras do README:
- **Uma linha na tabela de Regras por regra que existe no código**, com o mesmo `rule_code` do `metadata`, os mesmos parâmetros de `policy.py` (valor e unidade em reais, não em centavos) e o porquê de **cada** parâmetro (fonte regulatória, quando houver, ou a escolha de design e como foi calibrada). Número de norma só com a fonte primária conferida.
- Regra no código sem linha no README, ou linha no README sem regra no código, é bug. Um teste (`tests/unit/test_readme_rules.py`) lê o README e o `policy.py` e falha se os `rule_code` ou os valores divergirem.
- "Como as regras viram decisão": a matriz dos 3 eixos, os pisos regulatórios, os sinais de confiança, o cold start e exemplos de ponta a ponta (o payload de exemplo do desafio → `rejected`, com o porquê).
- "Como rodar e testar": do clone ao primeiro `curl` em poucos comandos, **com o header `INTERNAL-TOKEN` em todo exemplo**, o payload de exemplo do desafio pronto para colar, como rodar os testes e o farm. Testar numa máquina limpa antes do code freeze.
- Português, direto, sem enrolação. Toda mudança de regra ou parâmetro atualiza o README no mesmo PR.

## Fluxo de trabalho do time (vale para TODO agente, de qualquer pessoa)

Três pessoas, cada uma com o próprio Claude Code. **Ramon** é o integrador: revisa, aprova e faz o merge de todo PR. **Victoria** e **Natalia** desenvolvem tarefas do `TASKS.md` e abrem PR. Ninguém faz merge do próprio PR.

Regras para quem desenvolve uma tarefa:
1. **Uma tarefa = uma branch = um PR.** Branch a partir de `develop` atualizada: `feat/<ID>-<nome-curto>` (ex.: `feat/T07-get-pix-transaction`). PR sempre para `develop`.
2. **Só toque nos arquivos da tarefa.** Precisou mexer em outro arquivo (principalmente `database/database.sql`, `src/engine/risk_context.py`, `src/engine/policy.py`, `CLAUDE.md`, `docs/catalogo-de-erros.md`)? **Pare e pergunte ao Ramon.** Esses arquivos são contrato: mudança neles só pelo Ramon.
3. **Não invente regra de negócio, código de erro, parâmetro de política, tabela ou coluna.** Se a tarefa não diz, pergunte. Na dúvida entre duas leituras, escolha a mais conservadora e escreva a dúvida na descrição do PR.
4. **TDD:** o teste vem primeiro e está no mesmo PR. Antes de abrir o PR: `docker compose down -v && docker compose up -d`, todos os testes verdes (`pytest`), `flake8` limpo.
5. **README no mesmo PR:** tarefa que cria ou muda regra, parâmetro, rota ou comando atualiza a linha correspondente do README.md.
6. **PR pequeno** (idealmente < 300 linhas). Descrição do PR, nesta ordem: `Tarefa: <ID>` · o que foi feito · como testar (comandos) · arquivos tocados · dúvidas/decisões tomadas · o que ficou de fora.
7. Atualize o estado da sua tarefa no `TASKS.md` (a fazer → fazendo → em revisão) no próprio PR.
8. Bloqueou mais de 15 minutos? Avise o Ramon no grupo com o ID da tarefa. Não contorne o bloqueio mexendo em contrato.

Regras para o Ramon (integrador):
- Revisa em janelas curtas (~45 min), na ordem do `TASKS.md` (P0 antes). Confere: critério de pronto da tarefa, convenções deste arquivo, testes verdes, README atualizado, nenhum arquivo de contrato alterado sem combinar.
- Merge em `develop` com squash. `main` só recebe `develop` no code freeze (08:00).
- PR só de README ou de teste puro pode ser revisado pela outra colega; o Ramon é avisado e faz o merge.

## Tese

Não perguntamos "quão arriscado é". Perguntamos **qual é a dúvida**:
- **who** (device/canal/rede): é o cliente mesmo? → 2FA resolve
- **how** (valor, horário, comportamento do pagador): é normal pra ele? → 2FA resolve
- **where** (destino): o dinheiro vai pra golpe/mula? → 2FA NÃO resolve

## Convenções de código

- **Sem comentários.** O código fala por si: nomes claros, funções pequenas.
- **Tudo em inglês**, com os termos corretos de banco e risco (`payer`, `beneficiary`, `participant`, `branch`, `counterparty`). `translation` dos erros e dos reason codes em português.
- **Camadas, direção só para dentro:** `resource → controller → repository → model`. Repository só faz query; controller faz regra, monta o contexto, chama o motor e dá o commit; resource fala HTTP e decide o status; nenhum `raise` no resource. **Não existe camada `service`.**
- **`src/engine/` não é uma camada service:** não orquestra, não acessa banco, não chama HTTP, não lê relógio, não loga. É a política antifraude como **função pura** `evaluate(RiskContext) -> EngineResult`, chamada só pelo controller. Existe porque a política tem dezenas de regras e precisa ser testável e versionável fora do caminho de I/O.
- **Erros** no formato `{title, description, translation, code}`, prefixo **`RNV`**: `RNV000xxx` genéricos (reusar os do banco), `RNV001xxx` negócio. Os números são contrato estável entre os serviços do RNV: reusar o que já existe com o mesmo sentido, `RNV001039`–`RNV001044` já aprovados (ver catálogo); qualquer código além desses, me perguntar antes. Catálogo em `docs/catalogo-de-erros.md`.
- **JSON Schema na porta** valida a forma antes de qualquer consulta (400, códigos granulares `RNV000007`–`RNV000010`). Pydantic não é usado para contrato de entrada. O controller valida o sentido (422/409).
- **Enumeradores são tabelas de lookup** (`enumerator` UK + FK), nunca texto solto, `CHECK IN (...)` nem `ENUM` nativo. Valores em **minúsculo** (`approved`, `suspicious`, `pf_pf`); códigos (`RNV001039`, `HOW_NIGHT_LIMIT_EXCEEDED`) em maiúsculo.
- **Datas com fuso:** toda coluna de data é `TIMESTAMPTZ` (`DateTime(timezone=True)`). O fuso original do payload fica em `utc_offset_minutes`; a hora local é derivada.
- **Chaves:** `id` interno `BIGSERIAL` nas tabelas de volume (`SERIAL` nos lookups), nunca exposto e nunca usado em regra de negócio; ele é a PK e o alvo das FKs (8 bytes, inserção sequencial no fim do índice). Chave pública UUID v4 no tipo nativo `UUID` (16 bytes, `DEFAULT gen_random_uuid()`, `uq_pix_analysis_analysis_key`): `analysis_key`, o `key` da resposta. Nunca `CHAR(36)` (índice ~45% maior e comparação por collation) e nunca UUID como PK ou FK (v4 é aleatório: cada insert cai numa página qualquer do índice). O `id` do Pix vem do cliente e é guardado em `transaction_id`.
- **Dinheiro em centavos inteiros** (`*_minor`, `BIGINT`). O contrato externo chama `amount`; a coluna é `amount_minor`. Nunca float, nunca `round()`.
- **CPF/CNPJ mascarados** (pattern com pontuação; CNPJ aceita o formato alfanumérico). Coluna `VARCHAR(18)`.
- **Append-only:** transação e análise nunca mudam. Memória do motor (`account_device`, `account_counterparty`) é mutável e reconstruível a partir do registro.
- **Idempotência — na própria entidade:** `pix_transaction` carrega `transaction_id` (`UNIQUE` nomeado `uq_pix_transaction_transaction_id`) + `payload_hash` (`utils/payload_hash.py`, SHA-256 do JSON canônico). O insert do Pix é a primeira escrita; se o `UNIQUE` estourar: `rollback`, busca pela chave e compara o hash — igual, devolve a análise via DTO com `200`; diferente, `422 RNV001024`. **Sem `response_body` gravado**: a resposta é reconstruída do DTO (a análise é imutável, então é idêntica). Erros não são cacheados.
- **Concorrência:** conta via `INSERT ... ON CONFLICT DO NOTHING` + `SELECT`; incremento de memória atômico no SQL (`SET approved_count = approved_count + 1`). Sem lock de linha no caminho do motor (só leitura de histórico).
- **Consultas no caminho síncrono:** sempre igualdade numa entidade indexada + intervalo de `transaction_date` limitado (≤ 90 dias), só histórico anterior ao Pix analisado (nunca `now()`). Sem varredura, sem `GROUP BY` sem filtro. `latency_ms` gravada em cada análise (alvo < 100 ms).
- **Parâmetros de política** vivem em `src/engine/policy.py`, indexados por fluxo (`pf_pf`, `pf_pj`, `pj_pf`, `pj_pj`). Nenhum número mágico nas regras. Mudou parâmetro → sobe `POLICY_VERSION`.

## Contrato de rotas

| Rota | Acesso | Sucesso | Erros |
|---|---|---|---|
| `POST /pix/transaction` | serviço (`INTERNAL-TOKEN`) | `201 {key, status, metadata}`; retry idêntico `200` | 400 (`RNV000001`, `RNV000007`–`010`), 403 `RNV000002`, 422 (`RNV001002`, `RNV001020`, `RNV001024`, `RNV001040`–`RNV001043`), 409 `RNV001044` |
| `GET /pix/transaction/{id}` | serviço (`INTERNAL-TOKEN`) | `200 {key, status, metadata}` | 403 `RNV000002`, 404 `RNV001039` |
| `/`, `/health_check` | público | | |

**Autenticação:** o antifraude é chamado por outros serviços, então usa `INTERNAL-TOKEN` (403 `RNV000002`). Todo exemplo do README leva o header. O contrato completo das rotas vai para a seção `## Contrato da API` do README (não há `docs/rotas.md`).

## Como construir (ordem por fatia)

`database.sql` → `models/` → `repositories/` → `controllers/` (+ `errors/`) → `schemas/` (JSON) → `dtos/` → `resources/` + registro no `app.py` → testes. Registrar cada arquivo no `__init__.py` na ordem de dependência (evita circular import). O motor (`engine/`) é construído em paralelo, em TDD puro.

## Docker e banco

- `database/database.sql` roda **uma vez** na criação do volume. Mexeu no schema: `docker compose down -v && docker compose up`. Sem migration.
- **Seed:** só enumeradores e a tabela de referência `pix_participant` (469 ISPBs da Relação de participantes do STR, BCB, 16/10/2026, sem Selic/Bacen/STN, + o nosso fictício `99999999`). Nada de dado de transação no SQL: histórico vem do `scripts/farm.py`, pela própria API.
- `psycopg2-binary` pinado.

## Testes — TDD é o método

- **Integração:** caixa-preta, por HTTP, como cliente, com o harness de `tests/utils/` (`RequestGenerator`, `PayloadGenerator`, `RandomGenerator`); **nunca importa de `src/`**. Um teste = uma regra. Cobrir o caminho feliz e **cada** código de erro; checar `status` + `response["code"]`.
- **Unidade do motor (exceção controlada):** `tests/unit/engine/` pode importar **só** `src/engine/`, que é puro. Um teste por regra e por célula da matriz, montando `RiskContext` à mão. Não usa banco nem HTTP.
- **Cenários (personas):** sequências de Pix pela API com `transaction_date` no passado; viram teste de integração e alimentam o relatório de taxas por `policy_version`.
- Obrigatórios: payload de exemplo do desafio → `rejected`; 10x o mesmo `id` → uma análise; mesmo `id` com payload diferente → `422 RNV001024`; 1ª transação de cliente sem histórico nunca é `rejected` sem evidência em 2 eixos ou de outra entidade; persona legítima com 0 rejeições.
- Git: ver "Fluxo de trabalho do time". CI do GitHub Actions copiado do banco roda em todo PR.

## Fluxo do POST
1. Schema → 400
2. Validação de sentido no controller: dígito verificador CPF/CNPJ (422 `RNV001002`/`RNV001020`), `opening_date` ≤ `transaction_date`, `transaction_date` ≤ agora + 5 min, origem ≠ destino, IP que não parseia com `ipaddress` (422, `RNV001040`–`RNV001043`), conta conhecida com outro titular/abertura (409 `RNV001044`)
3. Insert do Pix (idempotência, ver Convenções)
4. Upsert de titulares e contas (`account_holder` por documento, `account` por banco + agência + número; origem usa `OWN_PARTICIPANT`); ISPB fora da lista não é erro: cria o participante com `listed = false` e vira o sinal `WHERE_UNKNOWN_PARTICIPANT`
5. Repositories montam o `RiskContext`
6. `engine.evaluate(context)` → `EngineResult`
7. Grava `pix_analysis`, `pix_analysis_axis` (3 linhas), `pix_analysis_rule` (todas as regras avaliadas: `fired`/`not_fired`/`unavailable`) e a memória (só se `approved`) → `commit`
8. `201 {key, status, metadata}`

## Modelo de dados (detalhe em `docs/modelo-de-dados.md`)
- Lookup: `pix_participant`, `person_type`, `analysis_status`, `decision_basis`, `risk_level`, `rule_axis`, `rule_outcome`
- Registro: `account_holder` (quem: documento + PF/PJ) · `account` (a conta: banco + agência + número + abertura, aponta para o titular) · `pix_transaction` · `pix_analysis` (1:1, a decisão) · `pix_analysis_axis` (3 linhas por análise: nível de who/how/where) · `pix_analysis_rule` (uma linha por regra avaliada)
- Memória: `account_device`, `account_counterparty` (só `approved`)
- View `pix_history` (transação + status)
- **Tabelas que crescem com o volume usam `BIGSERIAL`/`BIGINT`** (`account_holder`, `account`, `pix_transaction`, `pix_analysis`, `pix_analysis_axis`, `pix_analysis_rule`, `account_device`, `account_counterparty`) e toda FK para elas é `BIGINT`. Lookup fica em `SERIAL`/`INTEGER`.
- **Índices de janela são *covering*** (`INCLUDE`): as consultas de histórico leem só o índice (Index Only Scan, sem ir à tabela). Consulta nova de janela que precise de outra coluna: me pergunte antes de ir ao heap.
- **Toda consulta do caminho do POST/GET usa um identificador forte com índice** (chave natural `UNIQUE` ou índice `(entidade, transaction_date DESC)`). A tabela "caminho de acesso" em `docs/modelo-de-dados.md` lista cada consulta e o índice que ela usa; repository novo entra nessa tabela no mesmo PR. Consulta sem índice não passa na revisão.
- **Nenhuma regra de negócio usa o `id` serial:** não ordenar por `id`, não comparar `id`, não inferir "anterior/último" pelo `id` (o serial tem buracos e aceita insert manual). Ordem é sempre por `transaction_date`; identidade de negócio é a chave natural (`transaction_id`, ISPB + agência + conta, documento) ou a chave pública UUID.
- **Coluna mora na tabela da qual ela fala.** Antes de criar coluna, ler o nome da tabela e perguntar: "isso descreve essa coisa?". Documento e PF/PJ descrevem a pessoa (`account_holder`), não a conta; nível de cada eixo descreve um eixo da análise (`pix_analysis_axis`), não a análise.

### O que conta em cada consulta
| Uso | Status considerados | Por quê |
|---|---|---|
| Somas de limite (noturno, diário de device novo) | approved + two_factor_required | conservador: tudo que PODE ter saído |
| Velocity (tentativas) | todos | insistência é sinal |
| Fan-in do destino (pagadores distintos) | todos | campanha aparece nas tentativas |
| Rejeições no destino | rejected | "fundada suspeita" (Res. BCB 501/2025) |
| Teto do cliente, device confiável, destinatário recorrente | approved | conservador: só o que CERTAMENTE saiu |

## Motor
**Níveis por eixo:** `ok` / `suspicious` / `critical`.

**Matriz:** algum `critical` → rejected · 2+ eixos `suspicious` → rejected · 1 eixo `suspicious` → 2FA · tudo ok → approved.
**Pisos regulatórios** (mínimo 2FA): device sem histórico e valor > R$200; PF→PF noturno (20h–6h) somando > R$1.000.
**Confiança:** destinatário recorrente / self-Pix maduro com device confiável rebaixa UM `suspicious` para `ok` (nunca um `critical`).

**Cold start:** ausência de histórico nunca é evidência. Device novo só é suspeito se o pagador já tem outros devices. 1ª transação só é rejeitada por evidência do payload em 2 eixos ou por histórico de OUTRA entidade (device, destino, IP).

**Fases do pagador:** 0 (0 aprovadas) · 1 (1–4) · 2 (5+ aprovadas e 30+ dias) — teto = (n·teto_hist + 5·teto_ref)/(n+5).

**Device:** unknown → observing → trusted (1+ aprovada e 1ª vez há > 24h) · comprometido = 3+ documentos (critical).

| Eixo | Regras |
|---|---|
| who | device unknown com histórico do pagador · device 3+ docs / 2+ em 24h (critical) · agravantes: IP 5+ pagadores/1h, IP privado, IP estrangeiro (connector), geo parou de vir, geo fora do BR, geo distante + device unknown, canal novo (2+ agravantes → suspicious) |
| how | valor×horário (madrugada R$200–1k suspicious) · noturno PF→PF > R$1k · valor > teto do cliente · velocity 3+/10min (6+ critical) · retentativa < 10min após rejeição com valor menor |
| where | destino < 30 dias · ISPB fora da lista do STR (`WHERE_UNKNOWN_PARTICIPANT`) · destino < 30d com 3+ pagadores/24h (critical) · destino com 2+ rejeições de pagadores distintos/24h (critical, "fundada suspeita" Res. BCB 501/2025) |

**Falha do connector externo:** decide sem ele, registra em `metadata` (`ip_country: "unavailable"`).

## Princípios da política
1. **Regras por fluxo** (`flow` = `pf_pf`, `pf_pj`, `pj_pf`, `pj_pj`, derivado do formato do documento; não é gravado). Os parâmetros em `policy.py` são indexados por fluxo:
   | Parâmetro | PF→PF | PF→PJ | PJ→PF | PJ→PJ |
   |---|---|---|---|---|
   | Piso noturno R$1.000 (20h–6h) | sim (regulatório) | não (comércio noturno é normal) | não | não |
   | Piso device novo R$200/tx · R$1.000/dia | sim (pagador PF) | sim (pagador PF) | não | não |
   | Teto de referência (cold start) | por idade da conta origem | idem | R$20.000 | R$20.000 |
   | Fan-in crítico (destino < 30d) | 3+ pagadores/24h | 10+ (loja nova recebe de muitos; falsa loja recebe de muitos MAIS) | 3+ | 10+ |
   | Velocity do pagador | 3+/10min suspicious | idem | 20+/10min (folha de pagamento) | 20+/10min |
2. **Regras base (âncora regulatória):** limite noturno PF, limite de dispositivo não cadastrado, rejeição por fundada suspeita no destino (Res. BCB 501/2025). Só entra número de norma com a fonte primária aberta.
3. **Reason codes estruturados:** `EIXO_SINAL_DETALHE` em inglês (`WHO_DEVICE_UNKNOWN`, `HOW_NIGHT_LIMIT_EXCEEDED`, `WHERE_DESTINATION_FAN_IN`, `FLOOR_UNREGISTERED_DEVICE`, `TRUST_RECURRENT_BENEFICIARY`). Cada um carrega `level`, `observed`, `threshold`, `description` (EN) e `translation` (PT), igual aos erros do Base Service.
4. **Regras compostas em dois níveis:** dentro do eixo (condições com E: "Pix de teste" = valor baixo + valor alto em < 15 min para destino novo; "sondagem" = rejeição + nova tentativa menor em < 10 min) e entre eixos (a matriz: 2 eixos suspeitos = rejeição). Ex.: conta fantasma (mesmo titular + destino recém-aberto + device novo) não tem regra própria: sai da matriz.
5. **Custo esperado** é a justificativa teórica da matriz, não um cálculo em runtime (não temos p de fraude): 2FA domina quando ele resolve (dúvida de identidade); rejeitar domina quando 2FA não resolve (dúvida de destino).
6. **Cold start:** ausência de histórico nunca é evidência (ver Motor).
7. **Simulação:** personas (`scripts/farm.py`) medem taxa de 2FA e de rejeição por `policy_version`. Shadow mode só se sobrar tempo: engine é puro, então rodar uma política challenger e gravar o resultado em `features.shadow` custa pouco. Proxy label já usado como regra: retentativa menor após rejeição.
8. **Contra rule drift:** toda regra tem teste unitário + cenário; o relatório do simulador por versão tem orçamento (personas legítimas: 0 rejeições, ≤ 10% de 2FA); regra que nunca dispara nos cenários sai; mudar parâmetro = subir `policy_version`.
9. **Sem limite fixo para toda a base:** os únicos números absolutos são os regulatórios (são lei). O resto é relativo: teto do cliente, fluxo, idade das contas.
10. **Nada pesado no caminho síncrono:** toda consulta filtra por igualdade numa entidade indexada + intervalo de `transaction_date` limitado (≤ 90 dias); sem `GROUP BY` sem filtro, sem varredura; `latency_ms` gravada em cada análise (alvo < 100 ms).

## Formato do `metadata`
```json
{
  "policy_version": "2026.10.18-1",
  "flow": "pf_pf",
  "payer_maturity_phase": 0,
  "decision_basis": "two_suspicious_axes",
  "axes": {"who": "ok", "how": "suspicious", "where": "suspicious"},
  "reasons": [
    {"code": "HOW_NIGHT_LIMIT_EXCEEDED", "axis": "how", "level": "suspicious",
     "observed": {"night_amount": 150000}, "threshold": {"night_amount": 100000},
     "description": "Night-time amount between individuals above R$ 1,000.",
     "translation": "Soma noturna entre pessoas físicas acima de R$ 1.000."}
  ],
  "floors": ["FLOOR_UNREGISTERED_DEVICE"],
  "trust": []
}
```
`decision_basis` ∈ `critical_axis`, `two_suspicious_axes`, `single_suspicious_axis`, `regulatory_floor`, `trust_downgrade`, `clean`.

## Fora do escopo (descartado, com motivo no README)
Score por ISPB, Welford/perfil agregado, Redis, parâmetros de regra no banco, `invalid_requests`, viagem impossível, entropia de centavos, conta dormente, ML. Shadow mode só se sobrar tempo.

## Comandos
```bash
docker compose up
docker compose down -v && docker compose up
pip install -r requirements-dev.txt && pytest
python scripts/farm.py
```
