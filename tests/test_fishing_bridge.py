"""Offline subprocess tests: deliberately never send a connect command."""

import json
import os
import subprocess
import unittest

from src.fishing.bridge import BACKEND, BridgeError, FishingBridge


@unittest.skipUnless(
    os.name == "nt" and BACKEND.is_file(), "Build the optional Windows fishing backend first"
)
class FishingBridgeTest(unittest.TestCase):
    def test_identity_does_not_connect(self):
        result = subprocess.run(
            [str(BACKEND), "--identity"], capture_output=True, text=True, timeout=10
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual(
            {"protocol": 1, "upstream": "0.4.5", "injection": False}, json.loads(result.stdout)
        )

    def test_protocol_rejects_unconnected_start_and_still_shuts_down(self):
        bridge = FishingBridge()
        try:
            self.assertIsNone(bridge.request("status")["snapshot"])
            with self.assertRaises(BridgeError):
                bridge.request("start")
            with self.assertRaisesRegex(BridgeError, "Not connected"):
                bridge.request("configure", settings={})
            with self.assertRaisesRegex(BridgeError, "Unknown operation"):
                bridge.request("unknown")
            bridge.request("stop")
        finally:
            bridge.close()
        self.assertEqual(0, bridge.proc.returncode)

    def test_closed_input_exits_without_connecting(self):
        result = subprocess.run(
            [str(BACKEND), "--parent", str(os.getpid())],
            input="",
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(0, result.returncode)

    def test_malformed_input_fails_closed(self):
        result = subprocess.run(
            [str(BACKEND), "--parent", str(os.getpid())],
            input="not-json\n",
            text=True,
            capture_output=True,
            timeout=10,
        )
        messages = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertTrue(any(message.get("type") == "transport_error" for message in messages))

    def test_heartbeat_expiry_terminates_orphaned_backend(self):
        child = subprocess.Popen(
            [str(BACKEND), "--parent", str(os.getpid())],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            self.assertEqual(3, child.wait(timeout=12))
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=3)
            child.stdin.close()
            child.stdout.close()
            child.stderr.close()


if __name__ == "__main__":
    unittest.main()
