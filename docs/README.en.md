<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🌐 Tabbit Daily

**Two self-contained scripts for Tabbit China and International daily sign-in.**

[简体中文](../README.md) · **English** · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Português (BR)](README.pt-BR.md)

</div>

## Overview

| Script | Site | Account variable | Time zone |
| :--- | :--- | :--- | :--- |
| `tabbit_cn_daily.py` | `https://web.tabbit.com` | `TABBIT_CN_ACCOUNTS` | `Asia/Shanghai` |
| `tabbit_intl_daily.py` | `https://web.tabbit.ai` | `TABBIT_INTL_ACCOUNTS` | `UTC` |

The two sites use separate account systems. A token from one site is never reused by the other script.

## Sign-in Contract

```text
GET  /chat/sign-key
GET  /api/commerce/activity/v1/sign-in/status?scene_codes=daily_sign_in&scene_codes=desktop_pet
GET  /api/commerce/quota/v1/usage?user_id=...&timezone=...
POST /api/commerce/activity/v1/sign-in
```

The POST body contains a new UUID `request_no`, `scene_codes=["daily_sign_in"]`, and the current `usage_percentage`.

Only `sign_in_result=success` counts as a successful claim. `already_signed`, `signed_today=true`, and `activity_open=false` are neutral completion states.

## Account Format

```json
[
  {
    "name": "main",
    "cookie": "token=<JWT>; user_id=<USER_ID>",
    "unlock_pro": true
  }
]
```

`{"token":"<JWT>","uid":"<USER_ID>"}` is also accepted. The JWT is valid for about seven days and has no refresh endpoint.

## Commands

```text
python tabbit_cn_daily.py
python tabbit_cn_daily.py --query
python tabbit_cn_daily.py --only 2
python tabbit_cn_daily.py --no-notify
```

Use the same flags with `tabbit_intl_daily.py`.

## Notifications

Set any of `PUSHPLUS_TOKEN`, `BARK_URL`, or `WECOM_WEBHOOK`. Logs and notifications never print cookies, JWTs, or the full `user_id`.

## Verification

```text
python -m py_compile tabbit_cn_daily.py tabbit_intl_daily.py
python -m unittest discover -s tests -v
```

All tests use fake responses. They do not access a real Tabbit account.

Read [NOTICE.md](../NOTICE.md) before redistribution.
