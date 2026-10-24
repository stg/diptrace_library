"""Consistent terminal messages without making the library print anything."""
import sys


LEVELS = {"info": 0, "warning": 1, "error": 2}
PROCESSING_ERRORS = (OSError, ValueError, TypeError, LookupError, NotImplementedError)


def add_report_argument(parser, *, default="warning"):
    parser.add_argument(
        "--report-level", choices=LEVELS, default=default,
        help="minimum diagnostic level (default: warning); progress remains visible",
    )


class Console:
    """Filter diagnostics, leaving progress and completion messages visible.

    Informational output goes to stdout; warnings and errors go to stderr.
    Argument syntax and usage errors remain argparse's responsibility.
    """

    def __init__(self, report_level="warning"):
        self.minimum = LEVELS[report_level]

    def _write(self, level, message):
        stream = sys.stdout if level == "info" else sys.stderr
        print(f"{level.capitalize()}: {message}", file=stream, flush=True)

    def info(self, message):
        """Show an ordinary progress or completion message."""
        self._write("info", message)

    def diagnostic(self, severity, message):
        if LEVELS[severity] >= self.minimum:
            self._write(severity, message)

    def report(self, report, *, include_errors=True):
        for notice in report.notices:
            if notice.severity == "error" and not include_errors:
                continue
            source = notice.label or notice.file
            message = f"{source}: {notice.message}" if source else notice.message
            self.diagnostic(notice.severity, message)

    def failure(self, action, error, *, report=None):
        # A report's terminal error describes the exception about to be shown.
        # Retain preceding notices without printing that same failure twice.
        if report is not None:
            self.report(report, include_errors=False)
        self.diagnostic("error", f"{action}: {error}")
        return 1
