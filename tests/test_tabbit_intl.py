import unittest
from unittest import mock

from _loader import FakeResponse, FakeSession, load_script, sign_in_payload, status_payload


MODULE = load_script("tabbit_intl_behavior", "tabbit_intl_daily.py")


def account():
    return MODULE.account_from_payload(
        {"name": "intl", "token": "intl-token", "uid": "intl-user"},
        index=1,
        default_unlock_pro=True,
        default_client_version=MODULE.DEFAULT_CLIENT_VERSION,
    )


class InternationalBehaviorTests(unittest.TestCase):
    def test_intl_usage_url_uses_utc_and_intl_host(self):
        session = FakeSession(
            [
                FakeResponse(200, text="intl-sign-key"),
                FakeResponse(200, {"data": {"usage_percentage": 9.5}}),
            ]
        )
        client = MODULE.TabbitClient(account(), session=session)
        self.assertEqual("9.50%", client.query_usage_percentage())
        usage_call = session.calls[1]
        self.assertTrue(usage_call["url"].startswith("https://web.tabbit.ai/api/commerce/quota/v1/usage?"))
        self.assertIn("user_id=intl-user", usage_call["url"])
        self.assertIn("timezone=UTC", usage_call["url"])

    def test_intl_success_flow_never_calls_cn_host(self):
        class FakeClient:
            def __init__(self, _):
                self.usage = ""

            def query_status(self):
                return status_payload()

            def query_usage_percentage(self):
                return "8.00%"

            def claim(self, usage):
                self.usage = usage
                return sign_in_payload("success", "")

            def close(self):
                pass

        with mock.patch.object(MODULE, "TabbitClient", FakeClient):
            result = MODULE.process_account(account())
        self.assertEqual("success", result["outcome"])
        self.assertTrue(result["ok"])
        self.assertNotIn("web.tabbit.com", MODULE.BASE_URL)


if __name__ == "__main__":
    unittest.main()
