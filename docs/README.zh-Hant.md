<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🌐 Tabbit Daily

**分別維護 Tabbit 國內版與國際版登入態，完成每日 `daily_sign_in` 的單檔案腳本。**

[简体中文](../README.md) · [English](README.en.md) · **繁體中文** · [日本語](README.ja.md) · [한국어](README.ko.md) · [Português (BR)](README.pt-BR.md)

</div>

## 區域隔離

| 腳本 | 官方網域 | 帳號變數 | 時區 |
| :--- | :--- | :--- | :--- |
| `tabbit_cn_daily.py` | `https://web.tabbit.com` | `TABBIT_CN_ACCOUNTS` | `Asia/Shanghai` |
| `tabbit_intl_daily.py` | `https://web.tabbit.ai` | `TABBIT_INTL_ACCOUNTS` | `UTC` |

兩站登入態與簽名 key 不通用。腳本只讀取自身地區的帳號變數，不會跨區回退。

## 流程與判據

```text
GET  /chat/sign-key
GET  /api/commerce/activity/v1/sign-in/status?scene_codes=daily_sign_in&scene_codes=desktop_pet
GET  /api/commerce/quota/v1/usage?user_id=...&timezone=...
POST /api/commerce/activity/v1/sign-in
```

`POST` body 包含每次新生成的 `request_no`、`scene_codes=["daily_sign_in"]` 與 `usage_percentage`。

只有 `sign_in_result=success` 計為領取成功。`already_signed`、`signed_today=true`、`activity_open=false` 均為中性完成，不會重複提交。

## 帳號格式

```json
[
  {
    "name": "主帳號",
    "cookie": "token=<JWT>; user_id=<USER_ID>",
    "unlock_pro": true
  }
]
```

亦可用 `token + uid`，腳本會合成請求 Cookie。登入態約 7 天，沒有 refresh 介面。

## 指令

```text
python tabbit_cn_daily.py
python tabbit_cn_daily.py --query
python tabbit_cn_daily.py --only 2
python tabbit_cn_daily.py --no-notify
```

國際版參數相同。推送支援 `PUSHPLUS_TOKEN`、`BARK_URL`、`WECOM_WEBHOOK`。

## 驗證

```text
python -m py_compile tabbit_cn_daily.py tabbit_intl_daily.py
python -m unittest discover -s tests -v
```

所有測試均使用假回應，不存取真實帳號。轉載前請閱讀 [NOTICE.md](../NOTICE.md)。
