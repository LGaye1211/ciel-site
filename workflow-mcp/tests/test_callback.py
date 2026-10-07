import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from wfmcp.callback import make_handler
from wfmcp.engine import Engine
from wfmcp.store import Store
from wfmcp.teams import ConsoleNotifier

YAML = """
name: gate
version: 1
steps:
  - id: ok
    kind: approval
    title: Please approve
    channel: ops
"""


class CallbackTests(unittest.TestCase):
    def test_button_click_records_decision(self):
        notes = ConsoleNotifier()
        srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(None))
        port = srv.server_address[1]
        eng = Engine(Store(":memory:"), notes, callback_base=f"http://127.0.0.1:{port}", secret="s")
        srv.RequestHandlerClass = make_handler(eng)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        try:
            eng.register_type(YAML)
            run = eng.start("gate", {}, "me")
            approve_url = notes.sent[-1]["card"]["actions"][0]["url"]
            with urllib.request.urlopen(approve_url + "?by=alice@example.com") as r:
                self.assertEqual(r.status, 200)
                self.assertIn("Recorded: approved", r.read().decode())
            got = eng.get_run(run["id"])
            self.assertEqual(got["status"], "completed")
            self.assertEqual(got["steps"]["ok"]["outputs"]["decided_by"], "alice@example.com")
            # second click is refused, tampered link is refused
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(approve_url)
            self.assertEqual(cm.exception.code, 409)
            with self.assertRaises(urllib.error.HTTPError) as cm:
                urllib.request.urlopen(approve_url[:-4] + "zzzz")
            self.assertEqual(cm.exception.code, 409)
        finally:
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()
