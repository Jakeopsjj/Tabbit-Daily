# Changelog

## v1.0.1 - 2026-11-12

- claim 返回 `success` 后再次查询 `daily_sign_in`，仅 `signed_today=true` 才确认成功。
- 回读为 false、字段缺失或回读失败时标记 `pending_confirmation`，不再只凭 claim 回执报告成功。
- 报告新增独立“待确认”计数；新增 CN/INTL 回读回归，全套 `42` 项测试通过。

## v1.0.0 - 2026-11-04

- 新增 `tabbit_cn_daily.py`，固定使用 `https://web.tabbit.com` 与 `TABBIT_CN_ACCOUNTS`。
- 新增 `tabbit_intl_daily.py`，固定使用 `https://web.tabbit.ai` 与 `TABBIT_INTL_ACCOUNTS`。
- 实现 `daily_sign_in` 状态查询、百分比额度读取与签名签到。
- 仅把 `sign_in_result=success` 计为领取成功；`already_signed` 与活动未开启按中性完成处理。
- 支持 `--query`、`--only`、`--no-notify`、多账号、PushPlus、Bark 与企业微信。
- 加入日志与推送脱敏、响应大小限制、凭证格式校验和请求号去重。
- 新增 38 项假响应测试，覆盖区域隔离、身份冲突、签名、设备头、网络异常、重定向、401/403/429/499、重复 `request_no` 与并发状态。
- 当前未执行真实账号签到；真实奖励到账仍需账号持有人上线复验。
