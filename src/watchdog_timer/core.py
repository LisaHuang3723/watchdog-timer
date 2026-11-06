import threading


class WatchdogTimeout(Exception):
    """Raised by WatchdogTimer.check() when the timeout has elapsed."""


class WatchdogTimer:
    """A timer that runs a callback after a timeout unless reset.

    The timer arms itself on construction and after every reset(). If the
    timeout elapses without a reset, the callback runs exactly once on a
    daemon thread and the timer stops. Calling reset() after the callback has
    fired re-arms the timer.

    The clock is injectable so tests never depend on wall time. The default
    uses time.monotonic, which is immune to system clock adjustments.
    """

    def __init__(self, timeout, callback, clock=None):
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if not callable(callback):
            raise TypeError("callback must be callable")
        if clock is None:
            import time
            clock = time.monotonic
        self._timeout = float(timeout)
        self._callback = callback
        self._clock = clock
        self._lock = threading.Lock()
        self._thread = None
        self._deadline = None
        self._armed = False
        self._fired = False
        self._start()

    def _start(self):
        with self._lock:
            self._deadline = self._clock() + self._timeout
            self._armed = True
            self._fired = False
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def _run(self):
        while True:
            with self._lock:
                if not self._armed:
                    return
                remaining = self._deadline - self._clock()
            if remaining <= 0:
                break
            # Sleep in small slices so reset() and stop() are noticed promptly
            # without requiring a condition variable. The slice is capped so a
            # long timeout does not make reset() feel unresponsive.
            import time
            time.sleep(min(remaining, 0.01))
        with self._lock:
            if not self._armed:
                return
            self._armed = False
            self._fired = True
            cb = self._callback
        cb()

    def reset(self):
        """Restart the countdown. If the callback already fired, re-arms."""
        with self._lock:
            was_armed = self._armed
            if not was_armed:
                self._fired = False
            self._deadline = self._clock() + self._timeout
            self._armed = True
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, daemon=True)
                self._thread.start()

    def stop(self):
        """Disarm the timer. The callback will not run. Idempotent."""
        with self._lock:
            self._armed = False

    def check(self):
        """Raise WatchdogTimeout if the callback has fired, else return None.

        This is a polling helper for callers that prefer exceptions over
        callbacks. It does not affect the timer state.
        """
        with self._lock:
            if self._fired:
                raise WatchdogTimeout("watchdog timeout elapsed")

    @property
    def fired(self):
        """True once the callback has run and the timer has not been reset."""
        with self._lock:
            return self._fired

    @property
    def armed(self):
        """True while the timer is counting down toward the callback."""
        with self._lock:
            return self._armed

    def join(self, timeout=None):
        """Wait for the watchdog thread to finish. Intended for tests."""
        with self._lock:
            t = self._thread
        if t is not None:
            t.join(timeout)
