"""
QThread worker that runs the multi-stage email verifier over a
batch of collected emails, emitting progress signals to the GUI.
"""

from PySide6.QtCore import QThread, Signal

from app.core.pipeline import verify_all


class VerifierWorker(QThread):
    """
    Verifies a list of (email, source_url) pairs in a background thread.

    Signals
    -------
    progress : Signal(int, int)
        (completed_count, total_count) for the progress bar.
    result_ready : Signal(dict)
        Emitted per email with keys: email, source, status, error.
    finished : Signal(list)
        Emitted when all emails are verified with the full results list.
    """

    progress: Signal = Signal(int, int)
    result_ready: Signal = Signal(dict)
    verify_finished: Signal = Signal(list)

    def __init__(
        self,
        emails: list[tuple],
        smtp_enabled: bool = True,
        api_key: str | None = None,
    ) -> None:
        """
        Initialise the verifier worker.

        Parameters
        ----------
        emails : list[tuple]
            (email_address, source_url) pairs, or
            (email_address, source_url, evidence) triples. Both shapes
            are passed straight to `pipeline.verify_all`, which accepts
            either; evidence reaches the JSON and HTML exports and is
            not displayed (ADR-0014).
        smtp_enabled : bool
            If False, skip the SMTP handshake stage.
        api_key : str | None
            Enables Stage 4 API verification if provided.
        """
        super().__init__()
        self._emails = emails
        self._smtp_enabled = smtp_enabled
        self._api_key = api_key
        self._stop_flag = False

    def stop(self) -> None:
        """Signal the worker to stop after the current email."""
        self._stop_flag = True

    def run(self) -> None:
        """
        Consume the shared verification pipeline, emitting per-result
        signals. All verification logic lives in app.core.pipeline.
        """
        results: list[dict] = []
        total = len(self._emails)

        for i, record in enumerate(verify_all(
            self._emails,
            smtp_enabled=self._smtp_enabled,
            api_key=self._api_key,
        )):
            if self._stop_flag:
                break

            results.append(record)
            self.result_ready.emit(record)
            self.progress.emit(i + 1, total)

        self.verify_finished.emit(results)