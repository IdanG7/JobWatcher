"""A busy collector must not lose the browser's parallel startup connections."""
import socket
import unittest
from http.server import BaseHTTPRequestHandler

from dashboard import JobwatchHTTPServer


class StartupConnectionTests(unittest.TestCase):
    def test_browser_connection_burst_can_queue_before_accept_resumes(self):
        with JobwatchHTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler) as server:
            clients = []
            try:
                # Deliberately do not serve yet: simulate the collector holding
                # execution while a module graph's connections arrive together.
                for _ in range(24):
                    clients.append(socket.create_connection(server.server_address, timeout=0.5))
                self.assertEqual(24, len(clients))
            finally:
                for client in clients:
                    client.close()
