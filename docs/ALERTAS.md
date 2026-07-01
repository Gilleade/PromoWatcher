# Alertas — `alerts.json`

`alerts.json`, na raiz do projeto, é a fonte da verdade dos alertas.
O watcher recarrega o arquivo automaticamente quando ele é modificado
(sem precisar reiniciar) e sincroniza os alertas com a tabela `alerts`
do banco (necessário para o dashboard e para vincular cada promoção ao
alerta que a aprovou).

## Formato

```json
[
  {
    "name": "Notebook RTX 4050 até 4500",
    "enabled": true,
    "alert_type": "PRODUCT_RULE",
    "required": ["notebook", "rtx 4050"],
    "any": ["16gb", "512gb", "lenovo loq", "acer nitro", "asus tuf", "dell g15"],
    "exclude": ["rtx 3050", "gtx", "usado", "recondicionado", "peças", "capa"],
    "max_price": 4500,
    "min_discount_percent": 0,
    "bug_mode": false,
    "min_score": 70,
    "send_to_telegram": true
  }
]
```

## Campos

| Campo | Tipo | Descrição |
|---|---|---|
| `name` | string | Nome do alerta (usado como chave ao sincronizar com o banco — nomes devem ser únicos). |
| `enabled` | bool | Se `false`, o alerta é ignorado. |
| `alert_type` | string | `PRODUCT_RULE` ou `BUG_RULE` (informativo). |
| `required` | lista de strings | Todos os termos precisam aparecer na mensagem para o alerta bater. |
| `any` | lista de strings | Pelo menos um termo precisa aparecer (se a lista não for vazia). |
| `exclude` | lista de strings | Se qualquer termo aparecer, a mensagem é bloqueada (mesmo que `required`/`any` batam). |
| `max_price` | número ou `null` | Preço máximo aceito; se a mensagem não tiver preço identificável e `max_price` estiver definido, o score é penalizado. |
| `min_discount_percent` | número | Reservado para regras futuras de desconto mínimo. |
| `bug_mode` | bool | Marca o alerta como "possível bug" (aparece no dashboard). |
| `min_score` | inteiro | Score mínimo para o alerta ser considerado aprovado. |
| `send_to_telegram` | bool | Se `false`, a promoção é registrada mas não notificada. |

## Casamento de termos (`required`/`any`/`exclude`)

Os termos são comparados de forma tolerante a acentos, maiúsculas e
variações de espaço/hífen — por exemplo, o termo `"lava e seca"` casa
com "Lava e Seca", "lava-e-seca" ou "LAVA E SECA". Termos terminados em
"a" também casam com o plural (`"loucas"` casa com "louças" e
"louças").

## Score

Cada mensagem que bate com um alerta ganha uma pontuação explicável:

```text
+40 se todos os termos obrigatórios foram encontrados
+15 se algum termo opcional foi encontrado
+20 se o preço está abaixo do máximo definido
+15 se o texto contém "bug"/"provável bug"/"preço errado"
+10 se o link é de uma loja conhecida
-50 se contém termo bloqueado (exclude)
-30 se não foi possível identificar preço quando o alerta exige preço (max_price definido)
```

O motivo da aprovação/rejeição é sempre registrado (campo `reason`) e
aparece na notificação enviada e na aba "Promoções" da interface.

## Exemplo mínimo (paridade com o comportamento antigo)

O alerta abaixo reproduz o comportamento do antigo `keywords.txt`
(que continha apenas a palavra "bug"):

```json
{
  "name": "Possível BUG geral",
  "enabled": true,
  "alert_type": "BUG_RULE",
  "required": [],
  "any": ["bug"],
  "exclude": [],
  "max_price": null,
  "min_discount_percent": 0,
  "bug_mode": true,
  "min_score": 0,
  "send_to_telegram": true
}
```
