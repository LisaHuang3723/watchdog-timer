# watchdog-timer

Runs a callback after a specified timeout unless reset, using only the standard library.

```python
from watchdog_timer import WatchdogTimer, WatchdogTimeout

wd = WatchdogTimer(5.0, lambda: print("no heartbeat received"))
wd.reset()          # restart the countdown
wd.stop()           # disarm; the callback will not run
try:
    wd.check()      # raises WatchdogTimeout once the callback has fired
except WatchdogTimeout:
    pass
```

## Why this exists

A watchdog is a timer that expects to be reset. If the thing it watches goes
quiet, the timer fires. The common alternative is to track a deadline by hand
and poll it, which spreads the same three lines of bookkeeping across every
call site. This library keeps the deadline, the worker thread, and the fired
flag in one object.

The trade-off is that the timer owns a daemon thread. That makes `reset()`
cheap and the callback prompt, but it means a `WatchdogTimer` that is never
stopped or reset will keep a thread alive until the process exits. Call
`stop()` when the watched operation is done.

## The awkward edge

The callback runs on a background thread, not the thread that created the
timer. If the callback touches state that other threads also touch, protect
that state. `check()` is provided for callers that would rather poll for the
timeout on their own thread and raise an exception.

## API

- `WatchdogTimer(timeout, callback, clock=None)` — `timeout` is in seconds and
  must be positive. `callback` is called once when the timeout elapses.
  `clock` is an optional zero-argument callable returning a monotonically
  increasing float; it defaults to `time.monotonic` and exists so tests can
  supply a fake clock.
- `reset()` — restart the countdown. Re-arms the timer if it already fired.
- `stop()` — disarm the timer. Idempotent.
- `check()` — raise `WatchdogTimeout` if the callback has fired, else return
  `None`.
- `fired` — `True` once the callback has run and the timer has not been reset.
- `armed` — `True` while the timer is counting down.
- `join(timeout=None)` — wait for the worker thread to finish.
- `WatchdogTimeout` — exception raised by `check()`.
