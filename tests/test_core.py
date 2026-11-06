import threading
import unittest

from watchdog_timer import WatchdogTimer, WatchdogTimeout


class FakeClock:
    """A manually advanced clock. Thread-safe because the timer reads it
    from its worker thread while the test advances it from the main thread."""

    def __init__(self, start=0.0):
        self._now = start
        self._lock = threading.Lock()

    def __call__(self):
        with self._lock:
            return self._now

    def advance(self, delta):
        with self._lock:
            self._now += delta


class WatchdogTimerTests(unittest.TestCase):
    def test_callback_runs_after_timeout(self):
        clock = FakeClock()
        fired = threading.Event()
        wd = WatchdogTimer(1.0, fired.set, clock=clock)
        self.assertFalse(fired.is_set())
        clock.advance(1.5)
        self.assertTrue(fired.wait(2.0))
        wd.join(2.0)
        self.assertTrue(wd.fired)
        self.assertFalse(wd.armed)

    def test_reset_prevents_callback(self):
        clock = FakeClock()
        fired = threading.Event()
        wd = WatchdogTimer(1.0, fired.set, clock=clock)
        clock.advance(0.5)
        wd.reset()
        clock.advance(0.5)
        self.assertFalse(fired.wait(0.05))
        clock.advance(0.6)
        self.assertTrue(fired.wait(2.0))
        wd.join(2.0)

    def test_stop_disarms(self):
        clock = FakeClock()
        fired = threading.Event()
        wd = WatchdogTimer(1.0, fired.set, clock=clock)
        wd.stop()
        clock.advance(5.0)
        self.assertFalse(fired.wait(0.05))
        self.assertFalse(wd.fired)
        self.assertFalse(wd.armed)

    def test_check_raises_after_fire(self):
        clock = FakeClock()
        fired = threading.Event()
        wd = WatchdogTimer(1.0, fired.set, clock=clock)
        clock.advance(1.5)
        self.assertTrue(fired.wait(2.0))
        wd.join(2.0)
        with self.assertRaises(WatchdogTimeout):
            wd.check()

    def test_check_returns_none_before_fire(self):
        clock = FakeClock()
        wd = WatchdogTimer(1.0, lambda: None, clock=clock)
        self.assertIsNone(wd.check())
        wd.stop()

    def test_callback_runs_exactly_once(self):
        clock = FakeClock()
        calls = []
        done = threading.Event()

        def cb():
            calls.append(1)
            done.set()

        wd = WatchdogTimer(1.0, cb, clock=clock)
        clock.advance(1.5)
        self.assertTrue(done.wait(2.0))
        wd.join(2.0)
        self.assertEqual(len(calls), 1)

    def test_reset_after_fire_rearms(self):
        clock = FakeClock()
        first = threading.Event()
        second = threading.Event()
        calls = []

        def cb():
            calls.append(1)
            if len(calls) == 1:
                first.set()
            else:
                second.set()

        wd = WatchdogTimer(1.0, cb, clock=clock)
        clock.advance(1.5)
        self.assertTrue(first.wait(2.0))
        wd.join(2.0)
        wd.reset()
        self.assertTrue(wd.armed)
        self.assertFalse(wd.fired)
        clock.advance(1.5)
        self.assertTrue(second.wait(2.0))
        wd.join(2.0)
        self.assertEqual(len(calls), 2)

    def test_rejects_non_positive_timeout(self):
        with self.assertRaises(ValueError):
            WatchdogTimer(0, lambda: None)
        with self.assertRaises(ValueError):
            WatchdogTimer(-1.0, lambda: None)

    def test_rejects_non_callable_callback(self):
        with self.assertRaises(TypeError):
            WatchdogTimer(1.0, "not callable")

    def test_stop_is_idempotent(self):
        clock = FakeClock()
        wd = WatchdogTimer(1.0, lambda: None, clock=clock)
        wd.stop()
        wd.stop()
        self.assertFalse(wd.armed)
        self.assertFalse(wd.fired)

    def test_fired_property_false_while_armed(self):
        clock = FakeClock()
        wd = WatchdogTimer(1.0, lambda: None, clock=clock)
        self.assertTrue(wd.armed)
        self.assertFalse(wd.fired)
        wd.stop()


if __name__ == "__main__":
    unittest.main()
