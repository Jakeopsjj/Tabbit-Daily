<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🌐 Tabbit Daily

**Tabbit 中国版と国際版を分離して毎日 `daily_sign_in` を実行する単一ファイルスクリプト。**

[简体中文](../README.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md) · **日本語** · [한국어](README.ko.md) · [Português (BR)](README.pt-BR.md)

</div>

## リージョン分離

| スクリプト | サイト | アカウント変数 | タイムゾーン |
| :--- | :--- | :--- | :--- |
| `tabbit_cn_daily.py` | `https://web.tabbit.com` | `TABBIT_CN_ACCOUNTS` | `Asia/Shanghai` |
| `tabbit_intl_daily.py` | `https://web.tabbit.ai` | `TABBIT_INTL_ACCOUNTS` | `UTC` |

両サイトは別のアカウント体系です。Cookie、JWT、署名 key を相互利用しません。

## 処理

```text
GET  /chat/sign-key
GET  /api/commerce/activity/v1/sign-in/status?scene_codes=daily_sign_in&scene_codes=desktop_pet
GET  /api/commerce/quota/v1/usage?user_id=...&timezone=...
POST /api/commerce/activity/v1/sign-in
```

POST body は毎回新しい `request_no`、`scene_codes=["daily_sign_in"]`、`usage_percentage` を含みます。

`sign_in_result=success` のみ成功です。`already_signed`、`signed_today=true`、`activity_open=false` は中性完了です。

## アカウント

```json
[
  {
    "name": "main",
    "cookie": "token=<JWT>; user_id=<USER_ID>",
    "unlock_pro": true
  }
]
```

`token + uid` も利用できます。JWT は約 7 日有効で refresh API はありません。

## コマンド

```text
python tabbit_cn_daily.py
python tabbit_cn_daily.py --query
python tabbit_cn_daily.py --only 2
python tabbit_cn_daily.py --no-notify
```

国際版も同じ引数です。通知は PushPlus、Bark、WeCom に対応します。

## 検証

```text
python -m py_compile tabbit_cn_daily.py tabbit_intl_daily.py
python -m unittest discover -s tests -v
```

全テストは偽レスポンスを使用し、実アカウントへ接続しません。再配布前に [NOTICE.md](../NOTICE.md) を確認してください。
