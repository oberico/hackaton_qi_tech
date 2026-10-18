# Catálogo de erros — antifraude Pix

Mesmo formato e numeração do RNV (`oberico/desafio_qitech`, `docs/catalogo-de-erros.md`): `{title, description, translation, code}`. Números são contrato estável entre serviços: reusa o que já existe com o mesmo sentido; novos a partir de `RNV001039`.

## Reusados do RNV

| Código | HTTP | Quando |
|---|---|---|
| RNV000001 | 400 | corpo que não é objeto JSON |
| RNV000002 | 403 | `INTERNAL-TOKEN` ausente ou errado |
| RNV000004 | 404 | rota inexistente |
| RNV000005 | 405 | método não permitido |
| RNV000006 | 503 | pool de conexões esgotado |
| RNV000007 | 400 | campo obrigatório ausente |
| RNV000008 | 400 | campo não permitido (extra) |
| RNV000009 | 400 | tipo ou formato inválido (CPF/CNPJ sem máscara, data sem fuso, data impossível, ISPB fora de 8 dígitos) |
| RNV000010 | 400 | valor fora do limite (`amount` < 1, latitude/longitude fora da faixa, tamanhos) |
| RNV001002 | 422 | CPF com dígitos inválidos |
| RNV001020 | 422 | CNPJ inválido |
| RNV001024 | 422 | mesmo `id` de Pix reusado com conteúdo diferente |

## Novos (aprovados)

| Código | HTTP | Quando |
|---|---|---|
| RNV001039 | 404 | Pix com esse `id` não encontrado (GET) |
| RNV001040 | 422 | `opening_date` da conta depois de `transaction_date` |
| RNV001041 | 422 | `transaction_date` no futuro (tolerância de 5 min) |
| RNV001042 | 422 | conta de origem igual à de destino |
| RNV001043 | 422 | IP inválido |
| RNV001044 | 409 | conta já conhecida chegando com outro titular ou outra data de abertura |

## Não é erro
- ISPB fora da lista do STR: vira sinal de risco `WHERE_UNKNOWN_PARTICIPANT`.
- Canal desconhecido: vira agravante do eixo `who`.
