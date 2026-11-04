import unittest
from unittest import mock

from _loader import load_script, sign_in_payload, status_payload


MODULE = load_script("tabbit_cn_behavior", "tabbit_cn_daily.py")


def account(module, number=1):
    return module.account_from_payload(
        {"name": "account-%d" % number, "token": "token-%d" % number, "uid": "user-%d" % number},
        index=number,
        default_unlock_pro=True,
        default_client_version=module.DEFAULT_CLIENT_VERSION,
    )


class FakeClient:
    def __init__(self, status, usage="0.00%", claim=None, error=None):
        self.status = status
        self.usage = usage
        self.claim_payload = claim
        self.error = error
        self.claim_calls = 0
        self.usage_calls = 0
        self.closed = False

    def query_status(self):
        if self.error:
            raise self.error
        return self.status

    def query_usage_percentage(self):
        self.usage_calls += 1
        return self.usage

    def claim(self, usage_percentage):
        self.claim_calls += 1
        self.claim_usage = usage_percentage
        return self.claim_payload

    def close(self):
        self.closed = True


class ChinaBehaviorTests(unittest.TestCase):
    def run_with_client(self, fake, query_only=False):
        with mock.patch.object(MODULE, "TabbitClient", lambda _: fake):
            return MODULE.process_account(account(MODULE), query_only=query_only)

    def test_success_uses_usage_and_returns_reward(self):
        fake = FakeClient(
            status_payload(),
            usage="37.50%",
            claim=sign_in_payload("success", "reset_coupon"),
        )
        result = self.run_with_client(fake)
        self.assertEqual("success", result["outcome"])
        self.assertTrue(result["ok"])
        self.assertEqual("reset_coupon", result["reward"])
        self.assertEqual("37.50%", fake.claim_usage)
        self.assertEqual(1, fake.claim_calls)
        self.assertTrue(fake.closed)

    def test_already_signed_is_neutral_and_does_not_post(self):
        fake = FakeClient(status_payload(signed_today=True))
        result = self.run_with_client(fake)
        self.assertEqual("already_signed", result["outcome"])
        self.assertTrue(result["ok"])
        self.assertTrue(result["neutral"])
        self.assertEqual(0, fake.claim_calls)

    def test_activity_closed_is_neutral_and_does_not_post(self):
        fake = FakeClient(status_payload(activity_open=False))
        result = self.run_with_client(fake)
        self.assertEqual("activity_closed", result["outcome"])
        self.assertTrue(result["ok"])
        self.assertEqual(0, fake.claim_calls)

    def test_query_only_never_posts(self):
        fake = FakeClient(status_payload(), usage="12.00%")
        result = self.run_with_client(fake, query_only=True)
        self.assertTrue(result["ok"])
        self.assertEqual("query", result["outcome"])
        self.assertEqual("ready", result["status"])
        self.assertEqual("12.00%", result["usage_percentage"])
        self.assertEqual(0, fake.claim_calls)
        _, report = MODULE.build_report([result], query_only=True)
        self.assertIn("查询完成 1 · 失败 0", report)

    def test_upstream_reward_and_failure_text_is_redacted(self):
        success = FakeClient(
            status_payload(),
            claim=sign_in_payload("success", "token-1"),
        )
        success_result = self.run_with_client(success)
        self.assertNotIn("token-1", success_result["reward"])

        failed = FakeClient(
            status_payload(),
            claim=sign_in_payload("token-1", "skipped"),
        )
        failed_result = self.run_with_client(failed)
        self.assertNotIn("token-1", failed_result["message"])
        self.assertIn("<redacted>", failed_result["message"])

    def test_already_signed_claim_response_is_neutral(self):
        fake = FakeClient(
            status_payload(),
            usage="4.25%",
            claim=sign_in_payload("already_signed", "skipped"),
        )
        result = self.run_with_client(fake)
        self.assertEqual("already_signed", result["outcome"])
        self.assertTrue(result["ok"])
        self.assertTrue(result["neutral"])

    def test_usage_failure_uses_contract_zero_percent(self):
        fake = FakeClient(
            status_payload(),
            claim=sign_in_payload("success", "reset_coupon"),
        )
        fake.query_usage_percentage = mock.Mock(side_effect=MODULE.ApiError(502, "usage down"))
        result = self.run_with_client(fake)
        self.assertEqual("success", result["outcome"])
        self.assertEqual("0.00%", fake.claim_usage)

    def test_401_never_reaches_usage_or_claim(self):
        fake = FakeClient(
            status_payload(),
            error=MODULE.AuthError("登录状态失效"),
        )
        result = self.run_with_client(fake)
        self.assertEqual("auth_failed", result["outcome"])
        self.assertFalse(result["ok"])
        self.assertEqual(0, fake.usage_calls)
        self.assertEqual(0, fake.claim_calls)

    def test_one_network_failure_does_not_stop_following_accounts(self):
        class NetworkFailingClient(FakeClient):
            def __init__(self):
                super().__init__(status_payload())

            def query_status(self):
                raise MODULE.ApiError(0, "网络请求失败：Timeout")

        good = FakeClient(
            status_payload(),
            claim=sign_in_payload("success", ""),
        )
        with mock.patch.object(
            MODULE, "TabbitClient", side_effect=[NetworkFailingClient(), good]
        ):
            results = MODULE.run_accounts([account(MODULE, 1), account(MODULE, 2)])
        self.assertEqual(2, len(results))
        self.assertFalse(results[0]["ok"])
        self.assertEqual("failed", results[0]["outcome"])
        self.assertTrue(results[1]["ok"])
        self.assertEqual("success", results[1]["outcome"])


if __name__ == "__main__":
    unittest.main()
