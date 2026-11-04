<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🌐 Tabbit Daily

**Tabbit 중국판과 국제판을 분리해 매일 `daily_sign_in`을 실행하는 단일 파일 스크립트입니다.**

[简体中文](../README.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · **한국어** · [Português (BR)](README.pt-BR.md)

</div>

## 지역 분리

| 스크립트 | 사이트 | 계정 변수 | 시간대 |
| :--- | :--- | :--- | :--- |
| `tabbit_cn_daily.py` | `https://web.tabbit.com` | `TABBIT_CN_ACCOUNTS` | `Asia/Shanghai` |
| `tabbit_intl_daily.py` | `https://web.tabbit.ai` | `TABBIT_INTL_ACCOUNTS` | `UTC` |

두 사이트는 별도 계정 체계입니다. Cookie, JWT, 서명 키를 섞어 사용하지 않습니다.

## 처리 흐름

```text
GET  /chat/sign-key
GET  /api/commerce/activity/v1/sign-in/status?scene_codes=daily_sign_in&scene_codes=desktop_pet
GET  /api/commerce/quota/v1/usage?user_id=...&timezone=...
POST /api/commerce/activity/v1/sign-in
```

POST body에는 매번 새 `request_no`, `scene_codes=["daily_sign_in"]`, `usage_percentage`가 들어갑니다.

`sign_in_result=success`만 성공입니다. `already_signed`, `signed_today=true`, `activity_open=false`는 중립 완료로 처리합니다.

## 계정 형식

```json
[
  {
    "name": "main",
    "cookie": "token=<JWT>; user_id=<USER_ID>",
    "unlock_pro": true
  }
]
```

`token + uid`도 지원합니다. JWT는 약 7일 유효하며 refresh API가 없습니다.

## 명령

```text
python tabbit_cn_daily.py
python tabbit_cn_daily.py --query
python tabbit_cn_daily.py --only 2
python tabbit_cn_daily.py --no-notify
```

국제판도 동일한 인자를 사용합니다. 알림은 PushPlus, Bark, WeCom을 지원합니다.

## 검증

```text
python -m py_compile tabbit_cn_daily.py tabbit_intl_daily.py
python -m unittest discover -s tests -v
```

모든 테스트는 가짜 응답만 사용하며 실제 계정에 접속하지 않습니다. 재배포 전 [NOTICE.md](../NOTICE.md)를 읽어 주세요.
