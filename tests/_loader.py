import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name, filename):
    path = ROOT / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text
        if text:
            self.content = text.encode("utf-8")
        else:
            import json

            self.content = json.dumps(self._payload, separators=(",", ":")).encode("utf-8")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, "kwargs": kwargs})
        if not self.responses:
            raise AssertionError("unexpected request: %s %s" % (method, url))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def close(self):
        self.closed = True


def status_payload(activity_open=True, signed_today=False):
    return {
        "results": [
            {
                "scene_code": "desktop_pet",
                "activity_open": True,
                "signed_today": False,
            },
            {
                "scene_code": "daily_sign_in",
                "activity_open": activity_open,
                "signed_today": signed_today,
            },
        ]
    }


def sign_in_payload(result="success", reward="reset_coupon"):
    return {
        "results": [
            {
                "scene_code": "daily_sign_in",
                "sign_in_result": result,
                "usage_reward_result": reward,
            }
        ]
    }
