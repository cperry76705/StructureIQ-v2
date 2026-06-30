"""Optional background refresh loop for the read-only continuous research engine."""

from threading import Event, Lock, Thread

from core.research_engine import ResearchEngine, ResearchWindow


class ResearchScheduler:
    """Refresh research snapshots only after an explicit ``start`` call."""

    def __init__(self, engine: ResearchEngine) -> None:
        self._engine = engine
        self._stop = Event()
        self._thread: Thread | None = None
        self._lock = Lock()
        self._refresh_count = 0

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def refresh_count(self) -> int:
        return self._refresh_count

    def start(self, interval_seconds: float = 300.0) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        with self._lock:
            if self.is_running:
                return
            self._stop.clear()
            self._thread = Thread(
                target=self._run,
                args=(interval_seconds,),
                name="structureiq-research-refresh",
                daemon=True,
            )
            self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        with self._lock:
            thread = self._thread
            self._stop.set()
        if thread is not None:
            thread.join(timeout=timeout)

    def _run(self, interval_seconds: float) -> None:
        while not self._stop.wait(interval_seconds):
            self._engine.refresh(ResearchWindow.ALL_TIME)
            self._refresh_count += 1
