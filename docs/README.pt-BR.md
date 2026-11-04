<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🌐 Tabbit Daily

**Dois scripts autônomos para o check-in diário do Tabbit China e Internacional.**

[简体中文](../README.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · **Português (BR)**

</div>

## Separação regional

| Script | Site | Variável de conta | Fuso horário |
| :--- | :--- | :--- | :--- |
| `tabbit_cn_daily.py` | `https://web.tabbit.com` | `TABBIT_CN_ACCOUNTS` | `Asia/Shanghai` |
| `tabbit_intl_daily.py` | `https://web.tabbit.ai` | `TABBIT_INTL_ACCOUNTS` | `UTC` |

Os sites usam sistemas de conta diferentes. Cookie, JWT e chave de assinatura nunca são compartilhados entre os scripts.

## Fluxo

```text
GET  /chat/sign-key
GET  /api/commerce/activity/v1/sign-in/status?scene_codes=daily_sign_in&scene_codes=desktop_pet
GET  /api/commerce/quota/v1/usage?user_id=...&timezone=...
POST /api/commerce/activity/v1/sign-in
```

O corpo do POST contém um novo `request_no`, `scene_codes=["daily_sign_in"]` e `usage_percentage`.

Somente `sign_in_result=success` conta como sucesso. `already_signed`, `signed_today=true` e `activity_open=false` são conclusões neutras.

## Conta

```json
[
  {
    "name": "principal",
    "cookie": "token=<JWT>; user_id=<USER_ID>",
    "unlock_pro": true
  }
]
```

`token + uid` também é aceito. O JWT dura cerca de sete dias e não possui endpoint de renovação.

## Comandos

```text
python tabbit_cn_daily.py
python tabbit_cn_daily.py --query
python tabbit_cn_daily.py --only 2
python tabbit_cn_daily.py --no-notify
```

O script internacional usa os mesmos argumentos. Notificações: PushPlus, Bark e WeCom.

## Verificação

```text
python -m py_compile tabbit_cn_daily.py tabbit_intl_daily.py
python -m unittest discover -s tests -v
```

Todos os testes usam respostas falsas e não acessam uma conta real. Leia [NOTICE.md](../NOTICE.md) antes de redistribuir.
