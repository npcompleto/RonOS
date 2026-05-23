import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from config import logger

INTERVAL_PATTERN = re.compile(r"^(?P<value>\d+(?:\.\d+)?)(?P<unit>[smhd])?$", re.IGNORECASE)
UNIT_MULTIPLIER = {
    None: 1,
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
}


class JobScheduleError(Exception):
    pass


def parse_interval(interval: Any) -> float:
    """Normalizza un intervallo in secondi.

    Accetta:
    - numeri interi o float (secondi)
    - stringhe come '5m', '1h', '30s', '2d', '90'
    """
    if isinstance(interval, (int, float)):
        seconds = float(interval)
    elif isinstance(interval, str):
        match = INTERVAL_PATTERN.fullmatch(interval.strip())
        if not match:
            raise JobScheduleError(f"Intervallo non valido: {interval}")
        value = float(match.group("value"))
        unit = match.group("unit")
        seconds = value * UNIT_MULTIPLIER[unit.lower() if unit else None]
    else:
        raise JobScheduleError("L'intervallo deve essere un numero o una stringa come '5m'.")

    if seconds <= 0:
        raise JobScheduleError("L'intervallo deve essere maggiore di 0 secondi.")

    return seconds


class ScheduledJob:
    def __init__(
        self,
        name: str,
        target: Callable,
        interval: Any,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        initial_delay: Optional[Any] = None,
        run_immediately: bool = False,
    ):
        self.name = name
        self.target = target
        self.interval = parse_interval(interval)
        self.args = args or []
        self.kwargs = kwargs or {}
        self.initial_delay = parse_interval(initial_delay) if initial_delay is not None else None
        self.run_immediately = run_immediately

        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._stopped = threading.Event()
        self._next_run: Optional[float] = None

    def start(self) -> None:
        with self._lock:
            if self._timer is not None or self._stopped.is_set():
                return

            delay = 0 if self.run_immediately else (self.initial_delay if self.initial_delay is not None else self.interval)
            self._next_run = time.time() + delay
            logger.info(f"[Scheduler] Avvio job '{self.name}' con intervallo {self.interval}s, delay iniziale {delay}s")
            self._schedule_next(delay)

    def stop(self) -> None:
        with self._lock:
            self._stopped.set()
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            logger.info(f"[Scheduler] Job '{self.name}' fermato")

    def _schedule_next(self, delay: float) -> None:
        if self._stopped.is_set():
            return

        self._timer = threading.Timer(delay, self._run)
        self._timer.daemon = True
        self._timer.start()

    def _run(self) -> None:
        if self._stopped.is_set():
            return

        logger.info(f"[Scheduler] Esecuzione job '{self.name}'")
        start_ts = time.time()
        try:
            self.target(*self.args, **self.kwargs)
        except Exception as exc:
            logger.exception(f"[Scheduler] Errore durante l'esecuzione di '{self.name}': {exc}")
        finally:
            if self._stopped.is_set():
                return

            now = time.time()
            self._next_run = now + self.interval
            delay = max(self._next_run - now, 0)
            logger.debug(f"[Scheduler] Job '{self.name}' programmato di nuovo tra {delay:.2f}s")
            self._schedule_next(delay)

    def next_run(self) -> Optional[float]:
        return self._next_run


class JobScheduler:
    def __init__(self):
        self._jobs: Dict[str, ScheduledJob] = {}
        self._lock = threading.Lock()

    def add_job(
        self,
        name: str,
        target: Callable,
        interval: Any,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        initial_delay: Optional[Any] = None,
        run_immediately: bool = False,
    ) -> None:
        with self._lock:
            if name in self._jobs:
                raise JobScheduleError(f"Esiste già un job con il nome '{name}'")

            job = ScheduledJob(
                name=name,
                target=target,
                interval=interval,
                args=args,
                kwargs=kwargs,
                initial_delay=initial_delay,
                run_immediately=run_immediately,
            )
            self._jobs[name] = job
            logger.info(f"[Scheduler] Job '{name}' aggiunto")

    def remove_job(self, name: str) -> None:
        with self._lock:
            job = self._jobs.pop(name, None)
            if job:
                job.stop()
                logger.info(f"[Scheduler] Job '{name}' rimosso")

    def start(self) -> None:
        with self._lock:
            for job in self._jobs.values():
                job.start()
        logger.info("[Scheduler] Avvio di tutti i job completato")

    def stop(self) -> None:
        with self._lock:
            for job in list(self._jobs.values()):
                job.stop()
        logger.info("[Scheduler] Stop completo di tutti i job")

    def list_jobs(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {
                    "name": job.name,
                    "interval_seconds": job.interval,
                    "next_run": job.next_run(),
                }
                for job in self._jobs.values()
            ]

    def run_job_once(self, name: str) -> None:
        with self._lock:
            if name not in self._jobs:
                raise JobScheduleError(f"Job '{name}' non trovato")
            threading.Thread(target=self._jobs[name].target, args=tuple(self._jobs[name].args), kwargs=self._jobs[name].kwargs, daemon=True).start()


# Esempio d'uso:
#
# from jobs import JobScheduler
#
# def job1():
#     print("Eseguo job1")
#
# def job2():
#     print("Eseguo job2")
#
# scheduler = JobScheduler()
# scheduler.add_job("job1", job1, interval="1h", run_immediately=True)
# scheduler.add_job("job2", job2, interval="5m")
# scheduler.start()


if __name__ == "__main__":
    def sample_job(name: str) -> None:
        logger.info(f"Eseguo sample job: {name}")

    scheduler = JobScheduler()
    scheduler.add_job("job1", sample_job, interval="1h", args=["job1"], run_immediately=True)
    scheduler.add_job("job2", sample_job, interval="5m", args=["job2"], run_immediately=True)
    scheduler.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()
        logger.info("Scheduler terminato")
