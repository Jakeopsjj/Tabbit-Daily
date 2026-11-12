#!/usr/bin/env python3
"""
Tabbit 国际版每日签到 - 青龙单文件脚本

区域固定为 web.tabbit.ai。脚本只读取 TABBIT_INTL_ACCOUNTS，不会读取或回退到
国内版账号变量。登录态是约 7 天有效的 JWT，上游没有 refresh 接口。

命令：
    python tabbit_intl_daily.py
    python tabbit_intl_daily.py --query
    python tabbit_intl_daily.py --only 2
    python tabbit_intl_daily.py --no-notify
"""

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlencode

import requests


try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


SCRIPT_VERSION = "1.0.1"
REALM = "intl"
REALM_LABEL = "国际版"
BASE_URL = "https://web.tabbit.ai"
ACCOUNT_ENV = "TABBIT_INTL_ACCOUNTS"
TIME_ZONE = "UTC"

SIGN_KEY_PATH = "/chat/sign-key"
STATUS_PATH = (
    "/api/commerce/activity/v1/sign-in/status"
    "?scene_codes=daily_sign_in&scene_codes=desktop_pet"
)
SIGN_IN_PATH = "/api/commerce/activity/v1/sign-in"
USAGE_PATH = "/api/commerce/quota/v1/usage"

DEFAULT_CLIENT_VERSION = "1.17.16(10117016)"
DEFAULT_CLIENT_ID = "2dd8eb4c1ed9c344d173"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)
SEC_CH_UA = '"Tabbit Browser";v="149", "Chromium";v="149", "Not)A;Brand";v="24"'
WANTED_COOKIE_NAMES = ("token", "user_id", "managed", "NEXT_LOCALE", "SAPISID")
REQUEST_TIMEOUT = 20
MAX_RESPONSE_BYTES = 4 * 1024 * 1024

TRUE_TEXT = {"1", "true", "yes", "on", "开启", "是"}
FALSE_TEXT = {"0", "false", "no", "off", "关闭", "否"}
class TabbitError(RuntimeError):
    """Base error for a single account operation."""


class ConfigError(TabbitError):
    """Account configuration is missing or malformed."""


class CredentialError(TabbitError):
    """Cookie/JWT credentials are incomplete."""


class AuthError(TabbitError):
    """The site rejected the account login state."""


class ContractError(TabbitError):
    """The response does not match the observed sign-in contract."""


class ApiError(TabbitError):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class Account:
    index: int
    name: str
    token: str
    uid: str
    cookie: str
    unlock_pro: bool
    client_version: str


def log(message: str) -> None:
    print("%s %s" % (datetime.now().strftime("[%H:%M:%S]"), message), flush=True)


def env_value(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return default if value is None else value.strip()


def parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in TRUE_TEXT:
            return True
        if text in FALSE_TEXT:
            return False
    return default


def compact_text(value: Any, limit: int = 300) -> str:
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    return text[:limit]


def strip_bearer(value: str) -> str:
    text = str(value or "").strip()
    return text[7:].strip() if text.lower().startswith("bearer ") else text


def mask_identifier(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d{7,}", text):
        return text[:3] + "***" + text[-2:]
    if len(text) <= 8:
        return text[:2] + "***"
    return text[:4] + "***" + text[-2:]


def display_name(account: Account) -> str:
    name = account.name or "账号%d" % account.index
    if len(name) <= 12 and not re.search(r"\d{7,}", name):
        return name
    return mask_identifier(name)


def sanitize_message(text: str, account: Optional[Account] = None) -> str:
    value = compact_text(str(text or ""), 300)
    if not account:
        return value
    for secret in (account.token, account.cookie):
        if secret:
            value = value.replace(secret, "<redacted>")
    if account.uid:
        value = value.replace(account.uid, mask_identifier(account.uid))
    return value


def decode_jwt_claims(token: str) -> Dict[str, Any]:
    try:
        pieces = token.split(".")
        if len(pieces) < 2:
            return {}
        payload = pieces[1] + "=" * (-len(pieces[1]) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        claims = json.loads(decoded.decode("utf-8"))
        return claims if isinstance(claims, dict) else {}
    except Exception:
        return {}


def jwt_user_id(token: str) -> str:
    claims = decode_jwt_claims(token)
    for key in ("user_id", "uid", "sub", "userId"):
        value = claims.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()
    data = claims.get("data")
    if isinstance(data, dict):
        for key in ("user_id", "uid", "sub", "userId"):
            value = data.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()
    return ""


def extract_cookie(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    lower = text.lower()
    marker = lower.find("cookie:")
    if marker >= 0:
        rest = text[marker + len("cookie:") :].strip()
        end = len(rest)
        for char in ('"', "'", "\r", "\n"):
            found = rest.find(char)
            if found >= 0:
                end = min(end, found)
        candidate = rest[:end].strip()
        if "=" in candidate:
            return candidate
    marker = lower.find(" -b ")
    if marker >= 0:
        rest = text[marker + 4 :].strip()
        if rest:
            quote = rest[0] if rest[0] in ("'", '"') else ""
            if quote:
                candidate = rest[1:].split(quote, 1)[0].strip()
            else:
                candidate = rest.split(None, 1)[0].strip()
            if "=" in candidate:
                return candidate
    return text


def cookie_map(cookie: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for part in extract_cookie(cookie).split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip()
        if name and value:
            result[name] = value
    return result


def build_cookie(token: str, uid: str, raw_cookie: str = "") -> str:
    values = cookie_map(raw_cookie)
    values["token"] = token
    if uid:
        values.setdefault("user_id", uid)
        values.setdefault("SAPISID", uid)
    values.setdefault("managed", "tab_browser")
    values.setdefault("NEXT_LOCALE", "zh")
    return "; ".join(
        "%s=%s" % (name, values[name])
        for name in WANTED_COOKIE_NAMES
        if values.get(name)
    )


def account_from_payload(
    payload: Mapping[str, Any],
    index: int,
    default_unlock_pro: bool,
    default_client_version: str,
) -> Account:
    raw_cookie = payload.get("cookie") or ""
    raw_token = payload.get("token") or payload.get("accessToken") or payload.get("access_token") or ""
    uid = payload.get("uid") or payload.get("user_id") or payload.get("userId") or ""
    token = strip_bearer(str(raw_token or ""))
    cookie = extract_cookie(str(raw_cookie or ""))
    parsed_cookie = cookie_map(cookie)
    cookie_token = parsed_cookie.get("token", "").strip()
    if token and cookie_token and token != cookie_token:
        raise CredentialError("显式 token 与 Cookie 中的 token 不一致")
    if cookie_token:
        token = cookie_token
    if not token and cookie and "=" not in cookie:
        token = strip_bearer(cookie)
    if not token:
        raise CredentialError("缺少 Cookie 或 JWT（Cookie 中应有 token=...）")
    token = strip_bearer(token)
    if len(token) > 32768 or "\r" in token or "\n" in token:
        raise CredentialError("JWT 格式无效")
    explicit_uid = str(uid or "").strip()
    cookie_uid = parsed_cookie.get("user_id", "").strip()
    token_uid = jwt_user_id(token)
    uid_candidates = {
        value for value in (explicit_uid, cookie_uid, token_uid) if value
    }
    if len(uid_candidates) > 1:
        raise CredentialError("账号配置中的 user_id 与 JWT/Cookie 不一致")
    uid = next(iter(uid_candidates), "")
    if not uid:
        raise CredentialError("缺少 user_id，且 JWT 中没有可识别的用户标识")
    unlock_pro = parse_bool(
        payload.get("unlock_pro", payload.get("unlockPro")),
        default_unlock_pro,
    )
    client_version = str(
        payload.get("client_version")
        or payload.get("clientVersion")
        or default_client_version
    ).strip()
    if not client_version:
        client_version = DEFAULT_CLIENT_VERSION
    if len(client_version) > 80 or "\r" in client_version or "\n" in client_version:
        raise ConfigError("client_version 格式无效")
    cookie = build_cookie(token, uid, cookie)
    if len(cookie) > 32768 or "\r" in cookie or "\n" in cookie:
        raise CredentialError("Cookie 格式无效")
    name = compact_text(str(payload.get("name") or payload.get("note") or ""), 100)
    return Account(index, name or "账号%d" % index, token, uid, cookie, unlock_pro, client_version)


def account_from_text(
    raw: str,
    index: int,
    default_unlock_pro: bool,
    default_client_version: str,
) -> Account:
    text = str(raw or "").strip()
    if not text:
        raise CredentialError("账号内容为空")
    if text.startswith("{"):
        try:
            value = json.loads(text)
        except json.JSONDecodeError as error:
            raise ConfigError("JSON 账号格式错误: %s" % error) from error
        if not isinstance(value, dict):
            raise ConfigError("JSON 账号必须是对象")
        return account_from_payload(
            value, index, default_unlock_pro, default_client_version
        )
    if "|" in text:
        parts = [item.strip() for item in text.split("|", 3)]
        if len(parts) == 4:
            name, token, uid, client_version = parts
            return account_from_payload(
                {
                    "name": name,
                    "token": token,
                    "uid": uid,
                    "client_version": client_version,
                },
                index,
                default_unlock_pro,
                default_client_version,
            )
        if len(parts) == 3:
            name, token, uid = parts
            return account_from_payload(
                {"name": name, "token": token, "uid": uid},
                index,
                default_unlock_pro,
                default_client_version,
            )
        raise ConfigError("账号行应使用 name|token|uid 或 name|token|uid|client_version")
    payload = {"cookie": text} if "=" in text else {"token": text}
    return account_from_payload(
        payload, index, default_unlock_pro, default_client_version
    )


def load_accounts(
    raw: Optional[str] = None,
    default_unlock_pro: Optional[bool] = None,
    default_client_version: Optional[str] = None,
) -> List[Account]:
    source = env_value(ACCOUNT_ENV) if raw is None else str(raw)
    if not source.strip():
        raise ConfigError("未配置 %s" % ACCOUNT_ENV)
    if default_unlock_pro is None:
        default_unlock_pro = parse_bool(env_value("TABBIT_UNLOCK_PRO", "1"), True)
    if default_client_version is None:
        default_client_version = env_value("TABBIT_CLIENT_VERSION", DEFAULT_CLIENT_VERSION)
    items: List[Any]
    text = source.strip()
    parsed_json = False
    if text.startswith("[") or text.startswith("{"):
        try:
            value = json.loads(text)
            parsed_json = True
            if isinstance(value, list):
                items = value
            elif isinstance(value, dict) and isinstance(value.get("accounts"), list):
                items = value["accounts"]
            elif isinstance(value, dict):
                items = [value]
            else:
                raise ConfigError("账号 JSON 必须是对象或数组")
        except json.JSONDecodeError:
            items = [
                line.strip()
                for line in text.splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
    else:
        items = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    if not parsed_json and len(items) == 1 and "&&" in str(items[0]):
        items = [item.strip() for item in str(items[0]).split("&&") if item.strip()]
    accounts: List[Account] = []
    errors: List[str] = []
    for index, item in enumerate(items, 1):
        try:
            if isinstance(item, dict):
                account = account_from_payload(
                    item, index, default_unlock_pro, default_client_version
                )
            else:
                account = account_from_text(
                    str(item), index, default_unlock_pro, default_client_version
                )
            accounts.append(account)
        except TabbitError as error:
            errors.append("第 %d 条: %s" % (index, error))
    if errors:
        raise ConfigError("账号配置有误: %s" % "; ".join(errors[:3]))
    if not accounts:
        raise ConfigError("没有可用账号")
    return accounts


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def signature_headers(
    sign_key: str,
    body: bytes,
    now_ms: Optional[int] = None,
    request_uuid: Optional[str] = None,
) -> Dict[str, str]:
    timestamp = str(int(time.time() * 1000) if now_ms is None else int(now_ms))
    nonce_uuid = request_uuid or str(uuid.uuid4())
    message = "%s.%s.%s" % (timestamp, nonce_uuid, sha256_hex(body))
    nonce = hmac.new(
        sign_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return {
        "x-timestamp": timestamp,
        "x-signature": nonce_uuid,
        "x-nonce": nonce,
    }


def unique_uuid(
    default_browser: bool,
    now_ms: Optional[int] = None,
    random_value: Optional[bytes] = None,
) -> str:
    raw = random_value if random_value is not None else os.urandom(32)
    if len(raw) != 32:
        raise ValueError("random_value must contain 32 bytes")
    seconds = max(0, int(time.time() * 1000) if now_ms is None else int(now_ms)) // 1000
    timestamp = format(seconds, "08x")[-8:]
    positions = (2, 7, 11, 14, 18, 21, 25, 28)
    digits = "0123456789abcdef"
    non_one = "023456789abcdef"
    chars: List[str] = []
    for index in range(32):
        if index in positions:
            chars.append(timestamp[positions.index(index)])
        elif index == 5:
            chars.append("1" if default_browser else non_one[raw[index] % len(non_one)])
        else:
            chars.append(digits[raw[index] % len(digits)])
    text = "".join(chars)
    return "%s-%s-%s-%s-%s" % (
        text[0:8],
        text[8:12],
        text[12:16],
        text[16:20],
        text[20:32],
    )


def device_id(uid: str) -> str:
    digest = bytearray(hashlib.sha256(("tabbit-device:%s" % uid).encode("utf-8")).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    text = digest.hex()
    return "%s-%s-%s-%s-%s" % (
        text[0:8],
        text[8:12],
        text[12:16],
        text[16:20],
        text[20:32],
    )


def chrome_consistency(uid: str) -> str:
    return (
        "version=1,client_id=%s,device_id=%s,sync_account_id=%s,"
        "signin_mode=all_accounts,signout_mode=show_confirmation"
        % (DEFAULT_CLIENT_ID, device_id(uid), uid)
    )


def base_headers(account: Account, referer_path: str) -> Dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "sec-ch-ua": SEC_CH_UA,
        "sec-ch-ua-platform": '"Windows"',
        "sec-ch-ua-mobile": "?0",
        "x-chrome-id-consistency-request": chrome_consistency(account.uid),
        "referer": BASE_URL + referer_path,
        "Origin": BASE_URL,
        "x-req-ctx": base64.b64encode(account.client_version.encode("utf-8")).decode("ascii"),
        "unique-uuid": unique_uuid(account.unlock_pro),
    }


def make_sign_in_body(usage_percentage: str, request_no: Optional[str] = None) -> Dict[str, Any]:
    return {
        "request_no": request_no or str(uuid.uuid4()),
        "scene_codes": ["daily_sign_in"],
        "usage_percentage": usage_percentage,
    }


def json_body_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")


def format_usage_percentage(value: Any) -> str:
    try:
        number = float(str(value).strip().rstrip("%"))
    except (TypeError, ValueError, OverflowError):
        number = 0.0
    return "%.2f%%" % max(0.0, min(100.0, number))


def find_daily_entry(payload: Any) -> Mapping[str, Any]:
    if not isinstance(payload, dict):
        raise ContractError("响应不是 JSON 对象")
    results = payload.get("results")
    if not isinstance(results, list):
        raise ContractError("响应缺少 results 数组")
    for entry in results:
        if isinstance(entry, dict) and entry.get("scene_code") == "daily_sign_in":
            return entry
    raise ContractError("响应缺少 daily_sign_in 场景")


def interpret_status(payload: Any) -> Dict[str, Any]:
    entry = find_daily_entry(payload)
    activity_open = parse_bool(entry.get("activity_open"), True)
    signed_today = parse_bool(entry.get("signed_today"), False)
    if not activity_open:
        state = "activity_closed"
        message = "今日签到活动未开启"
    elif signed_today:
        state = "already_signed"
        message = "今日已签到"
    else:
        state = "ready"
        message = "今日尚未签到"
    return {
        "state": state,
        "activity_open": activity_open,
        "signed_today": signed_today,
        "message": message,
        "entry": entry,
    }


def interpret_sign_in(payload: Any) -> Dict[str, Any]:
    entry = find_daily_entry(payload)
    result = str(entry.get("sign_in_result") or "").strip()
    reward = compact_text(str(entry.get("usage_reward_result") or ""), 120)
    if reward.lower() == "skipped":
        reward = ""
    if result == "success":
        return {
            "outcome": "success",
            "ok": True,
            "neutral": False,
            "succeeded": True,
            "reward": reward,
            "message": "签到成功",
        }
    if result == "already_signed":
        return {
            "outcome": "already_signed",
            "ok": True,
            "neutral": True,
            "succeeded": False,
            "reward": "",
            "message": "今日已签到",
        }
    if not result:
        return {
            "outcome": "unknown",
            "ok": False,
            "neutral": False,
            "succeeded": False,
            "reward": "",
            "message": "上游没有给出明确的签到结论",
        }
    return {
        "outcome": "failed",
        "ok": False,
        "neutral": False,
        "succeeded": False,
        "reward": "",
        "message": "签到未成功: %s" % compact_text(result, 120),
    }


def pending_confirmation(
    message: str,
    reward: str = "",
    readback: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "outcome": "pending_confirmation",
        "ok": True,
        "neutral": True,
        "succeeded": False,
        "reward": reward,
        "message": message,
    }
    if readback is not None:
        result["readback"] = dict(readback)
    return result


def extract_usage_percentage(payload: Any) -> str:
    if not isinstance(payload, dict):
        raise ContractError("额度响应不是 JSON 对象")
    data = payload.get("data")
    if not isinstance(data, dict):
        data = payload
    value = data.get("usage_percentage")
    if value is None:
        value = data.get("usage")
    if value is None:
        raise ContractError("额度响应缺少 usage_percentage")
    return format_usage_percentage(value)


def response_bytes(response: Any) -> bytes:
    content = getattr(response, "content", None)
    if isinstance(content, bytes):
        return content
    text = getattr(response, "text", "")
    return text.encode("utf-8") if isinstance(text, str) else b""


def response_json(response: Any) -> Dict[str, Any]:
    payload = None
    try:
        payload = response.json()
    except Exception:
        payload = None
    return payload if isinstance(payload, dict) else {}


def error_text(payload: Mapping[str, Any]) -> str:
    for key in ("message", "msg", "detail", "error_message", "displayTips", "error"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return compact_text(value)
        if isinstance(value, dict):
            nested = value.get("message")
            if isinstance(nested, str) and nested.strip():
                return compact_text(nested)
    return ""


def raise_for_status(status: int, payload: Mapping[str, Any], account: Account) -> None:
    if 200 <= status < 300:
        return
    upstream = error_text(payload)
    if status in (401, 403):
        detail = upstream or "登录状态失效，可能使用了另一地区的令牌"
        raise AuthError(sanitize_message(detail, account))
    if status == 409:
        raise ApiError(status, "上游会话冲突，请稍后重试")
    if status == 429:
        raise ApiError(status, "请求过于频繁，请稍后重试")
    if status == 492:
        raise ApiError(status, "账号额度或会员权限不足")
    if status >= 500:
        raise ApiError(status, "上游服务异常（HTTP %d）" % status)
    raise ApiError(status, upstream or "请求失败（HTTP %d）" % status)


class TabbitClient:
    def __init__(self, account: Account, session: Optional[Any] = None, timeout: int = REQUEST_TIMEOUT):
        self.account = account
        self.timeout = timeout
        self.session = session or requests.Session()
        if session is None:
            self.session.trust_env = True
        self._sign_key = ""

    def close(self) -> None:
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    def _request(
        self,
        method: str,
        path: str,
        body: Optional[Mapping[str, Any]] = None,
        referer_path: str = "/member/usage",
        headers: Optional[Mapping[str, str]] = None,
        signed: bool = True,
    ) -> Tuple[int, Any]:
        request_headers = dict(headers or {})
        if signed:
            request_headers.update(base_headers(self.account, referer_path))
            request_headers["trace-id"] = str(uuid.uuid4())
            request_headers["Cookie"] = self.account.cookie
            request_headers["Authorization"] = "Bearer " + self.account.token
            body_bytes = b"" if body is None else json_body_bytes(body)
            request_headers.update(signature_headers(self.sign_key(), body_bytes))
        else:
            body_bytes = b"" if body is None else json_body_bytes(body)
        request_headers.setdefault("Accept", "application/json")
        if method.upper() == "POST":
            request_headers.setdefault("Content-Type", "application/json")
        kwargs: Dict[str, Any] = {
            "headers": request_headers,
            "timeout": self.timeout,
        }
        if body is not None:
            kwargs["data"] = body_bytes
        kwargs["allow_redirects"] = False
        try:
            response = self.session.request(
                method.upper(), BASE_URL + path, **kwargs
            )
        except requests.RequestException as error:
            raise ApiError(
                0, "网络请求失败：%s" % error.__class__.__name__
            ) from error
        content = response_bytes(response)
        if len(content) > MAX_RESPONSE_BYTES:
            raise ContractError("响应超过 4 MiB 上限")
        payload = response_json(response)
        raise_for_status(int(response.status_code), payload, self.account)
        return int(response.status_code), payload

    def sign_key(self, refresh: bool = False) -> str:
        if self._sign_key and not refresh:
            return self._sign_key
        headers = base_headers(self.account, "/")
        headers.update(
            {
                "Accept": "text/plain",
                "Cookie": self.account.cookie,
            }
        )
        try:
            response = self.session.request(
                "GET",
                BASE_URL + SIGN_KEY_PATH,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException as error:
            raise ApiError(
                0, "签名 key 网络请求失败：%s" % error.__class__.__name__
            ) from error
        status = int(response.status_code)
        text = response_bytes(response).decode("utf-8", errors="replace").strip()
        if status in (401, 403):
            raise AuthError("登录状态失效，可能使用了另一地区的令牌")
        if status != 200:
            raise ApiError(status, "签名 key 获取失败（HTTP %d）" % status)
        if (
            not text
            or len(text) > 512
            or any(char in text for char in '<> \n\r{}"')
        ):
            raise ContractError("签名 key 格式无效")
        self._sign_key = text
        return text

    def query_status(self) -> Dict[str, Any]:
        _, payload = self._request("GET", STATUS_PATH, referer_path="/member/usage")
        return payload

    def query_usage_percentage(self) -> str:
        query = urlencode({"user_id": self.account.uid, "timezone": TIME_ZONE})
        _, payload = self._request(
            "GET", USAGE_PATH + "?" + query, referer_path="/"
        )
        return extract_usage_percentage(payload)

    def claim(self, usage_percentage: str) -> Dict[str, Any]:
        body = make_sign_in_body(usage_percentage)
        _, payload = self._request(
            "POST", SIGN_IN_PATH, body=body, referer_path="/member/usage"
        )
        return payload


def process_account(account: Account, query_only: bool = False) -> Dict[str, Any]:
    client = TabbitClient(account)
    base_result: Dict[str, Any] = {
        "index": account.index,
        "name": display_name(account),
        "ok": False,
        "outcome": "failed",
        "neutral": False,
        "succeeded": False,
        "reward": "",
        "message": "",
    }
    try:
        status_payload = client.query_status()
        status = interpret_status(status_payload)
        base_result["status"] = status["state"]
        base_result["message"] = status["message"]
        if query_only:
            if status["state"] == "ready":
                try:
                    base_result["usage_percentage"] = client.query_usage_percentage()
                except TabbitError as error:
                    log(
                        "%s 额度查询失败，状态查询继续: %s"
                        % (base_result["name"], sanitize_message(str(error), account))
                    )
            base_result.update({"ok": True, "outcome": "query"})
            return base_result
        if status["state"] == "activity_closed":
            base_result.update(
                {"ok": True, "outcome": "activity_closed", "neutral": True}
            )
            return base_result
        if status["state"] == "already_signed":
            base_result.update(
                {"ok": True, "outcome": "already_signed", "neutral": True}
            )
            return base_result
        try:
            usage_percentage = client.query_usage_percentage()
        except TabbitError as error:
            usage_percentage = "0.00%"
            log(
                "%s 额度查询失败，按上游契约使用 0.00%%: %s"
                % (base_result["name"], sanitize_message(str(error), account))
            )
        base_result["usage_percentage"] = usage_percentage
        claim_payload = client.claim(usage_percentage)
        outcome = interpret_sign_in(claim_payload)
        if outcome["outcome"] == "success":
            try:
                readback_payload = client.query_status()
                readback = interpret_status(readback_payload)
            except TabbitError as error:
                outcome = pending_confirmation(
                    "签到请求已受理，状态回读失败，到账待确认",
                    outcome["reward"],
                    {
                        "scene_code": "daily_sign_in",
                        "error": sanitize_message(str(error), account),
                    },
                )
            else:
                evidence = {
                    "scene_code": "daily_sign_in",
                    "signed_today": readback["signed_today"],
                }
                if readback["signed_today"]:
                    outcome["message"] = "签到成功，状态回读 signed_today=true"
                    outcome["readback"] = evidence
                else:
                    outcome = pending_confirmation(
                        "签到请求已受理，状态回读尚未确认，待确认",
                        outcome["reward"],
                        evidence,
                    )
        outcome["message"] = sanitize_message(outcome["message"], account)
        outcome["reward"] = sanitize_message(outcome["reward"], account)
        base_result.update(outcome)
        base_result["status"] = outcome["outcome"]
        return base_result
    except AuthError as error:
        base_result.update(
            {
                "ok": False,
                "outcome": "auth_failed",
                "message": sanitize_message(str(error), account),
            }
        )
        return base_result
    except TabbitError as error:
        base_result.update(
            {
                "ok": False,
                "outcome": "failed",
                "message": sanitize_message(str(error), account),
            }
        )
        return base_result
    finally:
        client.close()


def run_accounts(accounts: Sequence[Account], query_only: bool = False) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for account in accounts:
        log("开始处理 %s" % display_name(account))
        result = process_account(account, query_only=query_only)
        results.append(result)
        reward = (" · 奖励 %s" % result["reward"]) if result.get("reward") else ""
        log("%s: %s%s" % (result["name"], result["message"] or result["outcome"], reward))
    return results


def notify_post(url: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
    session = requests.Session()
    try:
        response = session.post(url, json=dict(payload), timeout=15)
        return response_json(response)
    finally:
        session.close()


def notify_pushplus(title: str, content: str) -> bool:
    token = env_value("PUSHPLUS_TOKEN")
    if not token:
        return False
    try:
        result = notify_post(
            "https://www.pushplus.plus/send",
            {
                "token": token,
                "title": title,
                "content": content[:18000],
                "template": "markdown",
            },
        )
        return str(result.get("code")) == "200"
    except Exception:
        return False


def notify_bark(title: str, content: str) -> bool:
    endpoint = env_value("BARK_URL").rstrip("/")
    if not endpoint:
        return False
    try:
        result = notify_post(
            endpoint,
            {"title": title, "body": content[:12000], "group": "Tabbit"},
        )
        return result.get("code") == 200
    except Exception:
        return False


def notify_wecom(title: str, content: str) -> bool:
    hook = env_value("WECOM_WEBHOOK")
    if not hook:
        return False
    if not hook.startswith(("http://", "https://")):
        hook = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=" + hook
    try:
        result = notify_post(
            hook,
            {
                "msgtype": "text",
                "text": {"content": ("%s\n%s" % (title, content))[:3900]},
            },
        )
        return result.get("errcode") == 0
    except Exception:
        return False


def notify_all(title: str, content: str) -> None:
    configured = any(
        env_value(name)
        for name in ("PUSHPLUS_TOKEN", "BARK_URL", "WECOM_WEBHOOK")
    )
    if not configured:
        log("未配置 PushPlus / Bark / 企业微信，本次仅输出日志")
        return
    outcomes = (
        ("PushPlus", notify_pushplus(title, content)),
        ("Bark", notify_bark(title, content)),
        ("企业微信", notify_wecom(title, content)),
    )
    sent = [name for name, ok in outcomes if ok]
    if sent:
        log("通知已发送: %s" % ", ".join(sent))
    else:
        log("通知发送失败，账号结果仍以上方日志为准")


def build_report(results: Sequence[Mapping[str, Any]], query_only: bool) -> Tuple[str, str]:
    title = "Tabbit %s %s" % (REALM_LABEL, "状态查询" if query_only else "每日签到")
    lines = [title, ""]
    for result in results:
        suffix = ""
        if result.get("reward"):
            suffix += " · 奖励 %s" % result["reward"]
        if result.get("usage_percentage"):
            suffix += " · 用量 %s" % result["usage_percentage"]
        lines.append(
            "- %s: %s%s"
            % (result["name"], result.get("message") or result.get("outcome"), suffix)
        )
    if query_only:
        queried = sum(1 for result in results if result.get("ok"))
        failed = len(results) - queried
        summary = "查询完成 %d · 失败 %d" % (queried, failed)
    else:
        successes = sum(1 for result in results if result.get("outcome") == "success")
        pending = sum(
            1
            for result in results
            if result.get("outcome") == "pending_confirmation"
        )
        neutral = sum(
            1
            for result in results
            if result.get("outcome") in ("already_signed", "activity_closed")
        )
        failed = len(results) - successes - pending - neutral
        summary = "成功 %d · 待确认 %d · 中性 %d · 失败 %d" % (
            successes,
            pending,
            neutral,
            failed,
        )
    lines.extend(["", summary])
    return title, "\n".join(lines)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tabbit 国际版每日签到")
    parser.add_argument("--query", action="store_true", help="只查询状态，不发送签到请求")
    parser.add_argument("--only", type=int, metavar="N", help="只处理第 N 个账号（从 1 开始）")
    parser.add_argument("--no-notify", action="store_true", help="不发送通知")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        accounts = load_accounts()
    except ConfigError as error:
        log("配置错误: %s" % error)
        return 1
    if args.only is not None:
        if args.only < 1 or args.only > len(accounts):
            log("--only 超出范围: 1..%d" % len(accounts))
            return 2
        accounts = [accounts[args.only - 1]]
    log("╔════════════════════════════════════╗")
    log("║ 🌐 Tabbit 国际版 每日签到           ║")
    log("╚════════════════════════════════════╝")
    log("脚本 v%s · 账号数 %d · 区域 %s" % (SCRIPT_VERSION, len(accounts), BASE_URL))
    results = run_accounts(accounts, query_only=args.query)
    title, content = build_report(results, args.query)
    if not args.no_notify:
        notify_all(title, content)
    return 0 if all(result.get("ok") for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
