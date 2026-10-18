"""Regression tests for the 2026-10 reliability audit (batch 3): security and robustness."""
import http.client
import json
from http.server import ThreadingHTTPServer
import socket
import threading

from dashboard import ApiError, JobwatchHandler
from tests.app import test_dashboard as fixtures


class HttpHardeningTests(fixtures.ServiceFixture):
    call = fixtures.HttpApiTests.call

    def setUp(self):
        super().setUp()
        handler = type("H", (JobwatchHandler,), {"service": self.service})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def raw(self, method, path, body=b"", headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=10)
        self.addCleanup(conn.close)
        conn.request(method, path, body=body, headers={"Content-Type": "application/json", **(headers or {})})
        response = conn.getresponse()
        return response.status, response.read()

    def test_other_local_ports_are_cross_origin(self):
        port = self.server.server_port
        status, _ = self.call("POST", "/api/applications", {"key": "rbc:one", "status": "saved"},
                              {"Origin": f"http://127.0.0.1:{port + 1}"})
        self.assertEqual(403, status)
        status, _ = self.call("POST", "/api/applications", {"key": "rbc:one", "status": "saved"},
                              {"Origin": f"http://127.0.0.1:{port}"})
        self.assertEqual(200, status)
        status, _ = self.call("POST", "/api/applications", {"key": "rbc:one", "status": "saved"},
                              {"Sec-Fetch-Site": "same-site"})
        self.assertEqual(403, status)

    def test_content_type_must_be_json_itself(self):
        status, _ = self.raw("POST", "/api/applications", b'{"key":"rbc:one"}',
                             {"Content-Type": "text/plain; x=application/json"})
        self.assertEqual(415, status)

    def test_malformed_bodies_are_bad_requests(self):
        self.assertEqual(400, self.raw("POST", "/api/applications", b'{"key":"\xff"}')[0])
        self.assertEqual(400, self.raw("POST", "/api/applications", b"[" * 100_000)[0])

    def test_head_and_options_answer_instead_of_dropping(self):
        self.assertEqual(405, self.raw("HEAD", "/api/overview")[0])
        self.assertEqual(405, self.raw("OPTIONS", "/api/applications")[0])

    def test_bad_parameters_are_bad_requests(self):
        status, _ = self.call("GET", "/api/jobs?page=1e20")
        self.assertIn(status, (200, 400))       # clamped or refused, never a server error
        self.assertNotEqual(500, self.call("GET", "/api/jobs?per_page=abc")[0])

    def test_short_body_does_not_hold_the_thread(self):
        with socket.create_connection(("127.0.0.1", self.server.server_port), timeout=10) as sock:
            sock.sendall(b"POST /api/applications HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                         b"Content-Type: application/json\r\nContent-Length: 50\r\n\r\n{\"key\"")
            sock.shutdown(socket.SHUT_WR)
            self.assertIn(b"400", sock.recv(200))


class ServiceHardeningTests(fixtures.ServiceFixture):
    def test_csv_export_escapes_formulas(self):
        with self.service.db() as con:
            con.execute("UPDATE jobs SET title='=HYPERLINK(\"http://x\")' WHERE board='rbc' AND job_id='one'")
            con.execute("UPDATE job_intel SET facts_version=0 WHERE board='rbc' AND job_id='one'")
        self.service.refresh_now()
        text = self.service.csv_export({"include_hidden": ["1"], "all_sources": ["1"], "resume_match": ["0"]})
        self.assertIn("'=HYPERLINK", text)
        self.assertNotIn(',=HYPERLINK', text)

    def test_cover_letters_need_a_real_job(self):
        with self.assertRaises(ApiError):
            self.service.put_cover_letter("rbc:missing", {"body": "Dear team"})
        self.service.put_cover_letter("rbc:one", {"body": "Dear team"})

    def test_only_two_merges_run_at_once(self):
        self.service._merge_slots.acquire()
        self.service._merge_slots.acquire()
        try:
            with self.assertRaises(ApiError) as ctx:
                self.service.merge_documents({"files": [{"filename": "a.pdf", "data": ""}]})
            self.assertEqual(429, ctx.exception.status)
        finally:
            self.service._merge_slots.release()
            self.service._merge_slots.release()

    def test_hiding_a_job_does_not_run_a_full_refresh(self):
        calls = []
        self.service.refresh_now = lambda *a, **k: calls.append(1)
        self.service.set_override("rbc:one", {"hidden": True})
        self.service.watch_company("rbc", {"watched": True})
        self.assertEqual([], calls)
