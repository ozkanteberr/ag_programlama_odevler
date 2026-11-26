import unittest
from unittest.mock import patch

from dns_packet import A, NS, DNSError, Record, Response
from resolver import DNSResolver, ResolutionLimit


class ResolverTests(unittest.TestCase):
    @patch("resolver.read_hosts", return_value=[])
    def test_google_uses_root_glue_and_only_three_queries(self, hosts):
        responses = [
            Response([], [Record("com", NS, 60, "a.gtld-servers.net")],
                     [Record("a.gtld-servers.net", A, 60, "192.5.6.30")], False, 0),
            Response([], [Record("google.com", NS, 60, "ns1.google.com")],
                     [Record("ns1.google.com", A, 60, "216.239.32.10")], False, 0),
            Response([Record("google.com", A, 60, "142.250.187.14")], [], [], True, 0),
        ]
        with patch("resolver.query_server", side_effect=responses) as query:
            resolver = DNSResolver()
            self.assertEqual(resolver.resolve("google.com")[0], ["142.250.187.14"])
            resolver.resolve("google.com")
        self.assertEqual(query.call_count, 3)
        self.assertEqual([call.args[0] for call in query.call_args_list], ["google.com"] * 3)
        self.assertEqual(query.call_args_list[1].args[1], "192.5.6.30")

    def test_missing_glue_stops_after_first_success(self):
        response = Response([], [Record("example.com", NS, 60, "ns1.other.net"),
                                 Record("example.com", NS, 60, "ns2.other.net")], [], False, 0)
        resolver = DNSResolver()
        with patch.object(resolver, "resolve", return_value=(["192.0.2.1"], 60)) as lookup:
            self.assertEqual(resolver._referral("example.com", "com", response, set()),
                             ("example.com", ["192.0.2.1"]))
        lookup.assert_called_once_with("ns1.other.net", set())

    def test_unrelated_glue_is_not_trusted(self):
        response = Response([], [Record("example.com", NS, 60, "ns.other.net")],
                            [Record("ns.other.net", A, 60, "192.0.2.99")], False, 0)
        resolver = DNSResolver()
        with patch.object(resolver, "resolve", return_value=(["192.0.2.1"], 60)):
            self.assertEqual(resolver._referral("example.com", "com", response, set())[1],
                             ["192.0.2.1"])

    @patch("resolver.read_hosts", return_value=[])
    def test_timeout_queries_each_server_once(self, hosts):
        with patch("resolver.ROOT_SERVERS", ["192.0.2.1", "192.0.2.1"]), \
                patch("resolver.query_server", side_effect=DNSError("timeout")) as query:
            with self.assertRaises(DNSError):
                DNSResolver().resolve("google.com")
        self.assertEqual(query.call_count, 1)

    @patch("resolver.read_hosts", return_value=[])
    def test_nested_queries_share_budget(self, hosts):
        response = Response([], [Record("com", NS, 60, "ns.other.net")], [], False, 0)
        with patch("resolver.MAX_QUERIES", 1), \
                patch("resolver.query_server", return_value=response) as query:
            with self.assertRaises(ResolutionLimit):
                DNSResolver().resolve("google.com")
        self.assertEqual(query.call_count, 1)

    @patch("resolver.read_hosts", return_value=[])
    def test_deadline_stops_before_sending(self, hosts):
        with patch("resolver.time.monotonic", side_effect=[0, 31]), \
                patch("resolver.query_server") as query:
            with self.assertRaises(ResolutionLimit):
                DNSResolver().resolve("google.com")
        query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
