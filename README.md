<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🌐 Tabbit Daily

**分别维护 Tabbit 国内版与国际版登录态，安静完成每日 `daily_sign_in` 的单文件脚本。**

> 当前版本：**v1.0.1**（2026-11-12） · 最新更新：claim 后仅以 signed_today=true 回读确认签到成功

[简体中文](README.md) · [English](docs/README.en.md) · [繁體中文](docs/README.zh-Hant.md) · [日本語](docs/README.ja.md) · [한국어](docs/README.ko.md) · [Português (BR)](docs/README.pt-BR.md)

<p>
  <img src="https://img.shields.io/github/v/release/L0NE-6/Tabbit-Daily?style=for-the-badge&label=Release&color=2ea44f&logo=github" alt="Release" />
  <img src="https://img.shields.io/github/stars/L0NE-6/Tabbit-Daily?style=for-the-badge&label=Stars&color=FFC75F&logo=github" alt="Stars" />
  <img src="https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.8+" />
  <img src="https://img.shields.io/badge/%E9%9D%92%E9%BE%99-%E5%8D%95%E6%96%87%E4%BB%B6-4EAA25?style=for-the-badge" alt="Qinglong" />
  <img src="https://img.shields.io/badge/GitHub%20Actions-Supported-2088FF?style=for-the-badge&logo=githubactions&logoColor=white" alt="GitHub Actions" />
  <img src="https://img.shields.io/badge/License-MIT-F472B6?style=for-the-badge" alt="MIT License" />
  <a href="https://github.com/L0NE-6/Tabbit-Daily/releases"><img src="https://img.shields.io/badge/%E2%AC%87%20Download-Releases-2ea44f?style=for-the-badge&logo=github" alt="Download Releases" /></a>
</p>

[✨ 30 秒速览](#quick-overview) · [🌍 区域隔离](#regions) · [🚀 青龙部署](#quick-boot) · [☁️ Actions](#actions) · [🔐 账号格式](#credentials) · [🔧 环境变量](#environment) · [✅ 成功判据](#result) · [✦ 星轨](#star-trail)

</div>

---

<a id="policy"></a>
## 🚫 使用边界与转载声明

> [!IMPORTANT]
> 本项目仅供账号持有人维护自己的登录态与每日权益。请勿提交、截图或分享 Cookie、JWT、`user_id` 与账号导出文件。

仓库代码、部署说明与 Release 始终保持免费公开。未经作者明确书面许可，请勿把本项目包装成付费资源、内部版、独家版、会员权益、收费部署或包更新服务，也请勿删除作者与版权信息后冒充原创。完整规则见 [NOTICE.md](NOTICE.md)。

<a id="quick-overview"></a>
## ✨ 30 秒速览

| 维度 | 说明 |
| :--- | :--- |
| **用途** | 为 Tabbit 国内版或国际版账号执行每日签到，并回读当日状态。 |
| **输入** | `TABBIT_CN_ACCOUNTS` / `TABBIT_INTL_ACCOUNTS`，Cookie、JWT 或两者组合。 |
| **输出** | 活动状态、签到结论、额度奖励、脱敏后的账号摘要。 |
| **部署** | 青龙面板、GitHub Actions、Windows/macOS/Linux 本地 Python。 |
| **依赖** | Python 3.8+，仅需 `requests`。 |
| **成功判据** | 仅 `sign_in_result=success` 记为领取成功；`already_signed` 是中性完成。 |

<a id="regions"></a>
## 🌍 严格区域隔离

| 脚本 | 官方域名 | 账号变量 | 额度时区 | Provider |
| :--- | :--- | :--- | :--- | :--- |
| `tabbit_cn_daily.py` | `https://web.tabbit.com` | `TABBIT_CN_ACCOUNTS` | `Asia/Shanghai` | `tabbit` |
| `tabbit_intl_daily.py` | `https://web.tabbit.ai` | `TABBIT_INTL_ACCOUNTS` | `UTC` | `tabbit-intl` |

两站是独立账号体系。脚本不会读取另一地区的账号变量，也不会把一地 Cookie、JWT 或签名 key 回退复用到另一站点。把令牌放错脚本时，应按登录失效处理并重新导出对应站点登录态。

## 🔁 签到流程

```text
GET  /chat/sign-key
GET  /api/commerce/activity/v1/sign-in/status?scene_codes=daily_sign_in&scene_codes=desktop_pet
GET  /api/commerce/quota/v1/usage?user_id=...&timezone=...
POST /api/commerce/activity/v1/sign-in
```

签到请求体：

```json
{
  "request_no": "<每次新生成的 UUID>",
  "scene_codes": ["daily_sign_in"],
  "usage_percentage": "37.50%"
}
```

请求签名事实：

- `x-timestamp`：毫秒时间戳。
- `x-signature`：随机 UUID v4。命名与直觉相反，它不是 HMAC。
- `x-nonce`：`HMAC-SHA256(sign_key, "{timestamp}.{uuid}.{sha256hex(body)}")` 的小写 hex。
- GET 请求对空 body 签名；POST 对实际发送的 JSON 字节签名。
- 设备身份头包含 `x-req-ctx`、`unique-uuid`、`x-chrome-id-consistency-request` 与匹配的 User-Agent / Client Hints。

## 📦 文件说明

| 文件 | 用途 |
| :--- | :--- |
| `tabbit_cn_daily.py` | 国内版签到，固定 `web.tabbit.com`。 |
| `tabbit_intl_daily.py` | 国际版签到，固定 `web.tabbit.ai`。 |
| `requirements.txt` | Python 依赖。 |
| `tests/` | 全部基于假响应的契约、签名、区域隔离与状态测试。 |
| `.github/workflows/` | 每日运行与测试工作流。 |

<a id="quick-boot"></a>
## 🚀 青龙部署

1. 在青龙安装依赖或执行 `pip install -r requirements.txt`。
2. 上传需要地区对应的单文件脚本。
3. 在环境变量中添加 `TABBIT_CN_ACCOUNTS` 和/或 `TABBIT_INTL_ACCOUNTS`。
4. 建议把两个脚本拆成独立定时任务，首次先加 `--query` 验证登录态。

```text
# 北京时间每天 08:17，仅示例
17 8 * * * task tabbit_cn_daily.py
17 8 * * * task tabbit_intl_daily.py
```

两个站点的令牌不可混放。国内版只放国内账号，国际版只放国际账号。

<a id="actions"></a>
## ☁️ GitHub Actions

1. Fork 或导入仓库。
2. 在 **Settings → Secrets and variables → Actions** 添加账号与通知 Secrets。
3. 从 **Actions → Tabbit Daily → Run workflow** 先手动运行。
4. 默认 cron 为北京时间每天 08:17；GitHub schedule 是尽力触发，可能延迟。

| Secret | 必填 | 说明 |
| :--- | :---: | :--- |
| `TABBIT_CN_ACCOUNTS` | 可选 | 国内版账号；只跑国际版时留空。 |
| `TABBIT_INTL_ACCOUNTS` | 可选 | 国际版账号；只跑国内版时留空。 |
| `TABBIT_CLIENT_VERSION` | 可选 | 覆盖默认客户端版本。 |
| `TABBIT_UNLOCK_PRO` | 可选 | `unique-uuid` 默认浏览器标记，默认 `1`。 |
| `PUSHPLUS_TOKEN` | 可选 | PushPlus 微信推送。 |
| `BARK_URL` | 可选 | Bark 完整推送 URL。 |
| `WECOM_WEBHOOK` | 可选 | 企业微信群机器人完整 URL 或 key。 |

<a id="credentials"></a>
## 🔐 账号格式

推荐使用单行 JSON 数组。Cookie 中至少要有 `token` 与 `user_id`：

```json
[
  {
    "name": "主账号",
    "cookie": "token=<JWT>; user_id=<USER_ID>",
    "unlock_pro": true
  }
]
```

也支持 `token + uid`，脚本会按网页客户端形态合成请求 Cookie：

```json
[
  {
    "name": "备用账号",
    "token": "<JWT>",
    "uid": "<USER_ID>"
  }
]
```

青龙里也可用换行分隔：

```text
主账号|<JWT>|<USER_ID>
备用账号|<JWT>|<USER_ID>|1.17.16(10117016)
token=<JWT>; user_id=<USER_ID>
```

登录态约为 7 天有效的 JWT，上游没有 refresh 接口。过期后需从对应站点重新导出 Cookie 或 JWT。

显式 `token`、Cookie 内的 `token`、显式 `uid`、Cookie 内的 `user_id` 与 JWT 用户声明必须指向同一账号；发现冲突时脚本直接拒绝该账号，避免额度查询与签到串号。

<a id="environment"></a>
## 🔧 环境变量

| 变量 | 必填 | 默认 | 说明 |
| :--- | :---: | :--- | :--- |
| `TABBIT_CN_ACCOUNTS` | 国内脚本必填 | 空 | 只给 `tabbit_cn_daily.py`。 |
| `TABBIT_INTL_ACCOUNTS` | 国际脚本必填 | 空 | 只给 `tabbit_intl_daily.py`。 |
| `TABBIT_CLIENT_VERSION` | 可选 | `1.17.16(10117016)` | 全局客户端版本；账号项可单独覆盖。 |
| `TABBIT_UNLOCK_PRO` | 可选 | `1` | `unique-uuid` 的默认浏览器标记；账号项可单独覆盖。 |
| `PUSHPLUS_TOKEN` | 可选 | 空 | PushPlus。 |
| `BARK_URL` | 可选 | 空 | Bark。 |
| `WECOM_WEBHOOK` | 可选 | 空 | 企业微信群机器人。 |

## ⌨️ 命令行

```text
python tabbit_cn_daily.py                # 查询状态并签到
python tabbit_cn_daily.py --query        # 只查询，不发送签到 POST
python tabbit_cn_daily.py --only 2       # 只处理第 2 个账号
python tabbit_cn_daily.py --no-notify    # 不推送
```

国际版脚本参数完全一致。

<a id="result"></a>
## ✅ 成功判据与状态口径

| 上游状态 | 本地状态 | 说明 |
| :--- | :--- | :--- |
| `sign_in_result=success` 且回读 `signed_today=true` | 成功 | claim 后必须再次查询状态确认。 |
| `sign_in_result=already_signed` | 中性完成 | 今日已签，不重复领奖。 |
| `signed_today=true` | 中性完成 | 查询阶段已经确认今日签过，不再 POST。 |
| `activity_open=false` | 中性完成 | 活动未开启，不空打签到接口。 |
| claim success 但状态未确认 | 待确认 | 保留奖励文案，不报告已到账。 |
| 其他非空 `sign_in_result` | 失败 | 保留脱敏后的业务结论。 |
| 缺少 `daily_sign_in` 结果 | 失败 | 不以 HTTP 200 代替业务成功。 |

额度查询失败或缺少 `usage_percentage` 时，按已确认的上游契约使用 `0.00%`，并记录警告。签到 POST 不做自动重试，`request_no` 每次重新生成，避免并发或超时后重复提交。

## 🛡️ 隐私与脱敏

- 日志不打印 Cookie、JWT 或完整 `user_id`。
- 业务错误会先替换账号凭证，再截断输出。
- 推送内容只包含账号备注、状态、奖励和脱敏后的结果。
- HTTP 重定向一律拒绝，避免 307/308 重放签到 POST。
- `.env`、运行结果、缓存与 `__pycache__` 不应提交。

## 🧪 本地验证

```powershell
python -m py_compile tabbit_cn_daily.py tabbit_intl_daily.py
python -m unittest discover -s tests -v
```

测试不访问真实 Tabbit 接口，也不使用真实账号。当前覆盖国内/国际隔离、签名、设备头、请求体、重复请求号、401/403、缺 Cookie、成功/已签到、409 和并发状态隔离。

<a id="star-trail"></a>
## ✦ 星轨 Star Trail

[![Star History Chart](https://api.star-history.com/svg?repos=L0NE-6/Tabbit-Daily&type=Date)](https://star-history.com/#L0NE-6/Tabbit-Daily&Date)

## ☕ 支持与投喂

官方仓库与 Release 永久免费。以下二维码只用于自愿赞赏，不提供付费版本、代挂或账号保管服务。

<p align="center">
  <img src="assets/donate-wechat.png" alt="微信赞赏码" width="220" />
  <img src="assets/donate-alipay.jpg" alt="支付宝赞赏码" width="220" />
</p>

## 📄 License

代码以 [MIT License](LICENSE) 发布。仓库展示规则、作者身份与官方渠道说明见 [NOTICE.md](NOTICE.md)。本项目按公开协议事实独立实现，不包含或复制上游 AGPL 实现源码。

## 📦 版本与发布

- 当前发布版：`v1.0.1`（2026-11-12，签到后状态回读确认）。
