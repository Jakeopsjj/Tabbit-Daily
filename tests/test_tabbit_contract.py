import hashlib
import hmac
import json
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

import requests

from _loader import FakeResponse, FakeSession, load_script, sign_in_payload, status_payload


CN = load_script("tabbit_cn_contract", "tabbit_cn_daily.py")
INTL = load_script("tabbit_intl_contract", "tabbit_intl_daily.py")


class RegionContractTests(unittest.TestCase):
    def test_regions_use_separate_domains_and_account_variables(self):
        self.assertEqual("https://web.tabbit.com", CN.BASE_URL)
        self.assertEqual("TABBIT_CN_ACCOUNTS", CN.ACCOUNT_ENV)
        self.assertEqual("Asia/Shanghai", CN.TIME_ZONE)
        self.assertEqual("https://web.tabbit.ai", INTL.BASE_URL)
        self.assertEqual("TABBIT_INTL_ACCOUNTS", INTL.ACCOUNT_ENV)
        self.assertEqual("UTC", INTL.TIME_ZONE)

    def test_load_accounts_reads_only_its_own_region_variable(self):
        env = {
            "TABBIT_CN_ACCOUNTS": '[{"name":"cn","token":"cn-token","uid":"cn-user"}]',
            "TABBIT_INTL_ACCOUNTS": '[{"name":"intl","token":"intl-token","uid":"intl-user"}]',
        }
        with mock.patch.dict(os.environ, env, clear=False):
            cn_accounts = CN.load_accounts()
            intl_accounts = INTL.load_accounts()
        self.assertEqual(["cn"], [item.name for item in cn_accounts])
        self.assertEqual(["intl"], [item.name for item in intl_accounts])
        self.assertEqual("cn-token", cn_accounts[0].token)
        self.assertEqual("intl-token", intl_accounts[0].token)

    def test_conflicting_cookie_and_explicit_tokens_are_rejected(self):
        with self.assertRaises(CN.CredentialError):
            CN.account_from_payload(
                {
                    "token": "explicit-token",
                    "cookie": "token=cookie-token; user_id=user-1",
                },
                index=1,
                default_unlock_pro=True,
                default_client_version=CN.DEFAULT_CLIENT_VERSION,
            )

    def test_conflicting_cookie_and_explicit_user_ids_are_rejected(self):
        with self.assertRaises(CN.CredentialError):
            CN.account_from_payload(
                {
                    "token": "same-token",
                    "uid": "user-a",
                    "cookie": "token=same-token; user_id=user-b",
                },
                index=1,
                default_unlock_pro=True,
                default_client_version=CN.DEFAULT_CLIENT_VERSION,
            )

    def test_matching_cookie_and_explicit_identity_is_accepted(self):
        account = CN.account_from_payload(
            {
                "token": "same-token",
                "uid": "user-1",
                "cookie": "token=same-token; user_id=user-1",
            },
            index=1,
            default_unlock_pro=True,
            default_client_version=CN.DEFAULT_CLIENT_VERSION,
        )
        self.assertEqual("same-token", account.token)
        self.assertEqual("user-1", account.uid)

    def test_bad_account_is_not_silently_skipped(self):
        raw = (
            '[{"name":"good","token":"good-token","uid":"user-1"},'
            '{"name":"bad","uid":"user-2"}]'
        )
        with self.assertRaises(CN.ConfigError) as raised:
            CN.load_accounts(raw=raw)
        self.assertIn("第 2 条", str(raised.exception))


class CredentialTests(unittest.TestCase):
    def test_missing_cookie_and_token_is_rejected(self):
        with self.assertRaises(CN.CredentialError):
            CN.account_from_payload(
                {"uid": "user-1"},
                index=1,
                default_unlock_pro=True,
                default_client_version=CN.DEFAULT_CLIENT_VERSION,
            )

    def test_missing_cookie_is_synthesized_from_jwt_and_uid(self):
        account = CN.account_from_payload(
            {"token": "plain-jwt-value", "uid": "user-1"},
            index=1,
            default_unlock_pro=True,
            default_client_version=CN.DEFAULT_CLIENT_VERSION,
        )
        self.assertIn("token=plain-jwt-value", account.cookie)
        self.assertIn("user_id=user-1", account.cookie)
        self.assertIn("managed=tab_browser", account.cookie)

    def test_missing_user_id_is_rejected_when_jwt_has_no_claim(self):
        with self.assertRaises(INTL.CredentialError):
            INTL.account_from_payload(
                {"token": "not-a-jwt"},
                index=1,
                default_unlock_pro=True,
                default_client_version=INTL.DEFAULT_CLIENT_VERSION,
            )


class SignatureTests(unittest.TestCase):
    def test_signature_matches_hmac_contract_and_header_names(self):
        body = b'{"hello":"world"}'
        now_ms = 1700000000123
        request_uuid = "11111111-2222-4333-8444-555555555555"
        headers = CN.signature_headers("cn-sign-key", body, now_ms, request_uuid)
        message = "%d.%s.%s" % (
            now_ms,
            request_uuid,
            hashlib.sha256(body).hexdigest(),
        )
        expected = hmac.new(
            b"cn-sign-key", message.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        self.assertEqual(str(now_ms), headers["x-timestamp"])
        self.assertEqual(request_uuid, headers["x-signature"])
        self.assertEqual(expected, headers["x-nonce"])

    def test_signature_changes_with_body_and_realm_key(self):
        first = CN.signature_headers("key-a", b'{"a":1}', 1, str(uuid.uuid4()))
        second = CN.signature_headers("key-a", b'{"a":2}', 1, str(uuid.uuid4()))
        other_realm = INTL.signature_headers("key-b", b'{"a":1}', 1, str(uuid.uuid4()))
        self.assertNotEqual(first["x-nonce"], second["x-nonce"])
        self.assertNotEqual(first["x-nonce"], other_realm["x-nonce"])

    def test_unique_uuid_encodes_timestamp_and_browser_marker(self):
        raw = bytes(range(32))
        value = CN.unique_uuid(True, now_ms=1700000000123, random_value=raw)
        self.assertRegex(value, r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
        compact = value.replace("-", "")
        self.assertEqual("1", compact[5])
        timestamp = format(1700000000, "08x")[-8:]
        positions = (2, 7, 11, 14, 18, 21, 25, 28)
        self.assertEqual(list(timestamp), [compact[index] for index in positions])

    def test_device_id_is_stable_uuid(self):
        first = CN.device_id("user-1")
        second = CN.device_id("user-1")
        other = CN.device_id("user-2")
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertRegex(first, r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


class RequestContractTests(unittest.TestCase):
    def make_account(self, module, token="test-token", uid="user-1"):
        return module.account_from_payload(
            {"token": token, "uid": uid},
            index=1,
            default_unlock_pro=True,
            default_client_version=module.DEFAULT_CLIENT_VERSION,
        )

    def test_status_request_carries_signature_cookie_and_device_headers(self):
        session = FakeSession(
            [
                FakeResponse(200, text="cn-sign-key"),
                FakeResponse(200, status_payload()),
            ]
        )
        client = CN.TabbitClient(self.make_account(CN), session=session)
        payload = client.query_status()
        self.assertEqual("ready", CN.interpret_status(payload)["state"])
        self.assertEqual(2, len(session.calls))
        key_call, status_call = session.calls
        self.assertTrue(key_call["url"].endswith("/chat/sign-key"))
        self.assertNotIn("Authorization", key_call["kwargs"]["headers"])
        self.assertEqual("text/plain", key_call["kwargs"]["headers"]["Accept"])
        self.assertFalse(key_call["kwargs"]["allow_redirects"])
        headers = status_call["kwargs"]["headers"]
        self.assertTrue(status_call["url"].endswith(CN.STATUS_PATH))
        self.assertEqual("Bearer test-token", headers["Authorization"])
        self.assertIn("token=test-token", headers["Cookie"])
        self.assertIn("x-chrome-id-consistency-request", headers)
        self.assertIn("x-req-ctx", headers)
        self.assertIn("unique-uuid", headers)
        self.assertIn("sec-ch-ua", headers)
        self.assertIn("x-timestamp", headers)
        self.assertIn("x-signature", headers)
        self.assertIn("x-nonce", headers)
        self.assertFalse(status_call["kwargs"]["allow_redirects"])

    def test_status_signature_is_over_empty_body(self):
        session = FakeSession(
            [
                FakeResponse(200, text="cn-sign-key"),
                FakeResponse(200, status_payload()),
            ]
        )
        client = CN.TabbitClient(self.make_account(CN), session=session)
        client.query_status()
        headers = session.calls[1]["kwargs"]["headers"]
        message = "%s.%s.%s" % (
            headers["x-timestamp"],
            headers["x-signature"],
            hashlib.sha256(b"").hexdigest(),
        )
        expected = hmac.new(
            b"cn-sign-key", message.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        self.assertEqual(expected, headers["x-nonce"])

    def test_post_body_is_exact_signed_json(self):
        session = FakeSession(
            [
                FakeResponse(200, text="cn-sign-key"),
                FakeResponse(200, {"data": {"usage_percentage": 37.5}}),
                FakeResponse(200, sign_in_payload()),
            ]
        )
        client = CN.TabbitClient(self.make_account(CN), session=session)
        usage = client.query_usage_percentage()
        client.claim(usage)
        post_call = session.calls[2]
        body = post_call["kwargs"]["data"]
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual("/api/commerce/activity/v1/sign-in", post_call["url"].replace(CN.BASE_URL, ""))
        self.assertEqual("37.50%", payload["usage_percentage"])
        self.assertEqual(["daily_sign_in"], payload["scene_codes"])
        self.assertRegex(payload["request_no"], r"^[0-9a-f-]{36}$")
        headers = post_call["kwargs"]["headers"]
        message = "%s.%s.%s" % (
            headers["x-timestamp"],
            headers["x-signature"],
            hashlib.sha256(body).hexdigest(),
        )
        expected = hmac.new(
            b"cn-sign-key", message.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        self.assertEqual(expected, headers["x-nonce"])
        self.assertEqual("application/json", headers["Content-Type"])

    def test_request_numbers_are_unique(self):
        first = CN.make_sign_in_body("12.34%")
        second = CN.make_sign_in_body("12.34%")
        self.assertNotEqual(first["request_no"], second["request_no"])
        self.assertRegex(first["request_no"], r"^[0-9a-f-]{36}$")
        self.assertRegex(second["request_no"], r"^[0-9a-f-]{36}$")

    def test_401_and_403_are_auth_errors_and_do_not_post(self):
        for status in (401, 403):
            with self.subTest(status=status):
                session = FakeSession(
                    [
                        FakeResponse(200, text="cn-sign-key"),
                        FakeResponse(status, {"message": "expired"}),
                    ]
                )
                client = CN.TabbitClient(self.make_account(CN), session=session)
                with self.assertRaises(CN.AuthError):
                    client.query_status()
                self.assertEqual(2, len(session.calls))
                self.assertEqual("GET", session.calls[1]["method"])

    def test_409_is_reported_as_retryable_api_error(self):
        session = FakeSession(
            [
                FakeResponse(200, text="cn-sign-key"),
                FakeResponse(409, {"message": "busy"}),
            ]
        )
        client = CN.TabbitClient(self.make_account(CN), session=session)
        with self.assertRaises(CN.ApiError) as raised:
            client.query_status()
        self.assertEqual(409, raised.exception.status_code)

    def test_499_and_429_are_not_retried(self):
        for status in (499, 429):
            with self.subTest(status=status):
                session = FakeSession(
                    [
                        FakeResponse(200, text="cn-sign-key"),
                        FakeResponse(status, {"message": "fail"}),
                    ]
                )
                client = CN.TabbitClient(self.make_account(CN), session=session)
                with self.assertRaises(CN.ApiError) as raised:
                    client.query_status()
                self.assertEqual(status, raised.exception.status_code)
                self.assertEqual(2, len(session.calls))

    def test_redirect_response_never_replays_claim_post(self):
        session = FakeSession(
            [
                FakeResponse(200, text="cn-sign-key"),
                FakeResponse(200, {"data": {"usage_percentage": 12.0}}),
                FakeResponse(307, {"message": "redirect"}),
            ]
        )
        client = CN.TabbitClient(self.make_account(CN), session=session)
        usage = client.query_usage_percentage()
        with self.assertRaises(CN.ApiError):
            client.claim(usage)
        self.assertEqual(3, len(session.calls))
        self.assertEqual("POST", session.calls[2]["method"])
        self.assertFalse(session.calls[2]["kwargs"]["allow_redirects"])

    def test_network_exception_is_wrapped_and_not_retried(self):
        session = FakeSession(
            [
                FakeResponse(200, text="cn-sign-key"),
                requests.Timeout("slow"),
            ]
        )
        client = CN.TabbitClient(self.make_account(CN), session=session)
        with self.assertRaises(CN.ApiError) as raised:
            client.query_status()
        self.assertEqual(0, raised.exception.status_code)
        self.assertIn("Timeout", str(raised.exception))
        self.assertEqual(2, len(session.calls))


class ResponseSemanticsTests(unittest.TestCase):
    def test_status_states(self):
        self.assertEqual("ready", CN.interpret_status(status_payload())["state"])
        self.assertEqual(
            "already_signed",
            CN.interpret_status(status_payload(signed_today=True))["state"],
        )
        self.assertEqual(
            "activity_closed",
            CN.interpret_status(status_payload(activity_open=False))["state"],
        )

    def test_success_is_the_only_claimed_success(self):
        success = CN.interpret_sign_in(sign_in_payload("success", "reset_coupon"))
        already = CN.interpret_sign_in(sign_in_payload("already_signed", "skipped"))
        failed = CN.interpret_sign_in(sign_in_payload("risk_blocked", "skipped"))
        unknown = CN.interpret_sign_in({"results": [{"scene_code": "daily_sign_in"}]})
        self.assertTrue(success["succeeded"])
        self.assertTrue(success["ok"])
        self.assertEqual("reset_coupon", success["reward"])
        self.assertFalse(already["succeeded"])
        self.assertTrue(already["neutral"])
        self.assertFalse(failed["ok"])
        self.assertEqual("failed", failed["outcome"])
        self.assertEqual("unknown", unknown["outcome"])

    def test_usage_percentage_is_clamped_and_formatted(self):
        self.assertEqual("0.00%", CN.format_usage_percentage(-1))
        self.assertEqual("12.35%", CN.format_usage_percentage("12.345%"))
        self.assertEqual("100.00%", CN.format_usage_percentage(120))

    def test_concurrent_status_interpretation_has_no_shared_state(self):
        cases = [
            (status_payload(), "ready"),
            (status_payload(signed_today=True), "already_signed"),
            (status_payload(activity_open=False), "activity_closed"),
            (status_payload(), "ready"),
        ]
        with ThreadPoolExecutor(max_workers=4) as executor:
            states = list(
                executor.map(
                    lambda payload: CN.interpret_status(payload)["state"],
                    [payload for payload, _ in cases],
                )
            )
        self.assertEqual([expected for _, expected in cases], states)


if __name__ == "__main__":
    unittest.main()
