import time
import unittest
from unittest import mock

from _loader import load_script


MODULE = load_script("tabbit_cn_concurrency", "tabbit_cn_daily.py")


def account(number):
    return MODULE.account_from_payload(
        {"token": "token-%d" % number, "uid": "user-%d" % number},
        index=number,
        default_unlock_pro=True,
        default_client_version=MODULE.DEFAULT_CLIENT_VERSION,
    )


class ConcurrencyStateTests(unittest.TestCase):
    def test_run_accounts_is_serial_to_avoid_overlapping_sign_in(self):
        events = []

        def fake_process(item, query_only=False):
            events.append(("start", item.index))
            time.sleep(0.02)
            events.append(("end", item.index))
            return {"index": item.index, "name": item.name, "ok": True, "outcome": "success", "message": "ok"}

        with mock.patch.object(MODULE, "process_account", fake_process):
            results = MODULE.run_accounts([account(1), account(2)])
        self.assertEqual(2, len(results))
        self.assertEqual(
            [
                ("start", 1),
                ("end", 1),
                ("start", 2),
                ("end", 2),
            ],
            events,
        )


if __name__ == "__main__":
    unittest.main()
