"""
QThread worker that runs the multi-stage email verifier over a
batch of collected emails, emitting progress signals to the GUI.
"""

from PySide6.QtCore import QThread, Signal

from app.core.verifier import verify, VStatus


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
        emails: list[tuple[str, str]],
        smtp_enabled: bool = True,
        api_key: str | None = None,
    ) -> None:
        """
        Initialise the verifier worker.

        Parameters
        ----------
        emails : list[tuple[str, str]]
            List of (email_address, source_url) pairs to verify.
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
        """Verify all emails and emit results."""
        results = []
        total = len(self._emails)

        for i, (email, source) in enumerate(self._emails):
            if self._stop_flag:
                break

            vr = verify(
                email,
                smtp_enabled=self._smtp_enabled,
                api_key=self._api_key,
            )

            status_str = {
                VStatus.VALID:   'valid',
                VStatus.INVALID: 'invalid',
                VStatus.UNKNOWN: 'unknown',
            }[vr.status]

            record = {
                'email':  email,
                'source': source,
                'status': status_str,
                'error':  vr.error,
            }

            results.append(record)
            self.result_ready.emit(record)
            self.progress.emit(i + 1, total)

        self.verify_finished.emit(results)