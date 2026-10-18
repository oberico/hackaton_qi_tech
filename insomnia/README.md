# Coleção do Insomnia

Testes manuais e de carga do motor antifraude, no estilo do pytest, mas pela interface.

## Importar

1. Suba a API: `docker compose up -d` (API em `http://localhost:8001`).
2. Insomnia → Create → Import → `insomnia/antifraud-pix.insomnia.json`.
3. A URL (`http://localhost:8001`) e o token (`internal-token-dev`) estão escritos direto em cada requisição; não depende de ambiente. O ambiente "Base Environment" existe só como referência.

## Pastas

| Pasta | O que mostra | Esperado |
|---|---|---|
| 0. Saúde | `/` e `/health_check` | 200 |
| 1. Payload do desafio | o exemplo do desafio e o GET dele | 201 `rejected` |
| 2. Idempotência | POST, repetido, mesmo id com payload diferente, GET | 201, 200, 422 `RNV001024`, 200 |
| 3. Erros de formato e token | 400 `RNV000001`, `007`–`010`, 403 `RNV000002`, 404 `RNV001039` | conforme o nome da requisição |
| 4. Erros de sentido | 422 `RNV001002`, `001020`, `001040`–`001043`, 409 `RNV001044` | conforme o nome da requisição |
| 5. Decisões do motor | approved, piso de device, 2FA, ISPB fora da lista, noturno, velocity, fan-in, device compartilhado | na descrição de cada requisição |
| 6. Carga e latência | pagadores distintos, rajada de um pagador, campanha de fan-in | 201 em todas; latência < 100 ms |

Cada requisição traz o resultado esperado na descrição. As pastas do item 5 dependem das regras entregues (T08, T14, T16) e do histórico (T10, T15): antes disso, algumas decisões serão mais brandas.

## Carga com o Runner

Não precisa de arquivo de dados: cada requisição da pasta usa `{% uuid 'v4' %}` (id e device) e `{% now 'millis' %}` (conta de origem nova), então cada iteração é um pagador novo.

1. Clique com o botão direito na pasta **6. Carga e latência** → Run (Collection Runner).
2. **A** e **C**: Iterations = 200, Delay = 0 a 50 ms.
3. **B**: Iterations = 20, Delay = 0 (rajada de um pagador só; deve escalar para 2FA e depois rejected).
4. A tabela do Runner mostra status e tempo de cada resposta.

## Conferido e não conferido

- Os 42 corpos de POST foram validados contra `src/schemas/post_pix_transaction.json`: os de erro de formato falham no schema e os demais passam. Os CPF e CNPJ usam dígitos válidos, exceto os propositalmente inválidos.
- A importação no app do Insomnia não foi testada nesta máquina (o formato é o de exportação v4). As tags `{% uuid 'v4' %}` e `{% now 'millis' %}` da pasta de carga são a parte mais frágil; se alguma não resolver na tua versão, me diga a mensagem de erro.
