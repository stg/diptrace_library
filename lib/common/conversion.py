"""Shared import/export diagnostics distinguish normalization from meaningful loss."""
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from functools import wraps
from inspect import signature
import warnings


@dataclass(frozen=True)
class ConversionNotice:
    rule: str
    destination: str
    message: str
    paths: tuple[str, ...] = ()
    recoverability: str = 'not preserved in destination'
    severity: str = 'warning'
    operation: str = 'export'
    file: str | None = None
    label: str | None = None

    def __post_init__(self):
        if self.severity not in ('info', 'warning', 'error'):
            raise ValueError('conversion severity must be info, warning or error')
        if self.operation not in ('import', 'export'):
            raise ValueError('conversion operation must be import or export')

    @property
    def format(self):
        """Input or output format; destination remains a compatible alias."""
        return self.destination


class ConversionWarning(UserWarning):
    def __init__(self, notice):
        self.notice = notice
        count = f' ({len(notice.paths)} records)' if notice.paths else ''
        super().__init__(f'{notice.destination}: {notice.message}{count} [{notice.rule}]')


@dataclass
class ConversionReport:
    """Ordered diagnostics; collection suppresses automatic Python warnings.

    An error is recorded before its original exception is raised. Collecting a
    report never permits invalid input or output to continue.
    """
    notices: list[ConversionNotice] = field(default_factory=list)

    def clear(self) -> None:
        """Discard collected notices before starting another operation or batch."""
        self.notices.clear()

    @property
    def infos(self):
        return [notice for notice in self.notices if notice.severity == 'info']

    @property
    def warnings(self):
        return [notice for notice in self.notices if notice.severity == 'warning']

    @property
    def errors(self):
        return [notice for notice in self.notices if notice.severity == 'error']


# One report type for both operations. Keep the established export spelling.
ExportReport = ConversionReport
ImportReport = ConversionReport
_import_session = ContextVar('design_import_diagnostics', default=None)
_export_session = ContextVar('design_export_diagnostics', default=None)


@dataclass(frozen=True)
class _Session:
    report: ConversionReport | None
    format: str
    start: int
    file: str | None = None
    label: str | None = None


def _file_reader(operation):
    """Locate an actual path parameter once, never treating buffer data as a path."""
    parameters = tuple(signature(operation).parameters)
    position = parameters.index('path') if 'path' in parameters else None
    def read(args, kwargs):
        path = kwargs.get('path')
        if path is None and position is not None and position < len(args):
            path = args[position]
        return str(path) if path is not None else None
    return read


def _label(kwargs):
    label = kwargs.pop('label', None)
    if label is not None and not isinstance(label, str):
        raise TypeError('diagnostic label must be text')
    return label


def import_notice(severity, rule, message, nodes=(), *, recoverability='current design data retained'):
    """Record modernization without storing its history in design properties."""
    session = _import_session.get()
    if session is not None:
        notice = ConversionNotice(rule, session.format, message, tuple(node.path for node in nodes),
                                  recoverability, severity, 'import', session.file, session.label)
        if notice not in session.report.notices[session.start:]:
            session.report.notices.append(notice)


def _set_import_format(format):
    """Attribute a detected adapter to the current file/buffer import session."""
    session = _import_session.get()
    if session is not None:
        _import_session.set(replace(session, format=format or 'unknown'))


def import_diagnostics(format=None):
    """Collect one boundary report across parsing and semantic modernization."""
    def decorate(operation):
        file = _file_reader(operation)
        @wraps(operation)
        def run(*args, **kwargs):
            report = kwargs.pop('report', None)
            label = _label(kwargs)
            if report is not None and not isinstance(report, ConversionReport):
                raise TypeError('report must be a ConversionReport')
            # A normal import can call a raw parser and source-view conversion.
            # Only its outer boundary collects diagnostics and handles errors.
            if report is None and label is None and _import_session.get() is not None:
                return operation(*args, **kwargs)
            key = format or kwargs.get('format')
            if key is None:
                source = args[0] if args else kwargs.get('path')
                key = getattr(source, 'representation', None)
                path = file(args, kwargs)
                if key is None and path is not None:
                    from pathlib import Path
                    key = Path(path).suffix
            key = (key or 'unknown').lower().lstrip('.')
            collected = report if report is not None else ConversionReport()
            start = len(collected.notices)
            token = _import_session.set(_Session(collected, key, start, file(args, kwargs), label))
            try:
                document = operation(*args, **kwargs)
                for message in document.diagnostics:
                    if not any(n.operation == 'import' and n.message == message for n in collected.notices[start:]):
                        import_notice('warning', 'import-diagnostic', message)
                for issue in document.references.issues:
                    import_notice(issue.severity, 'unresolved-reference', issue.message, (issue.source,),
                                  recoverability='unresolved identity remains available for investigation and editing')
                if report is None:
                    for notice in collected.notices[start:]:
                        if notice.severity == 'warning':
                            warnings.warn(ConversionWarning(notice), stacklevel=2)
                return document
            except Exception as error:
                import_notice('error', 'import-failed', str(error),
                              recoverability='import aborted; no design returned')
                raise
            finally:
                _import_session.reset(token)
        return run
    return decorate


def export_diagnostics(destination=None):
    """Collect adapter failures while preserving existing exception types."""
    def decorate(operation):
        file = _file_reader(operation)
        @wraps(operation)
        def run(*args, **kwargs):
            report = kwargs.get('report')
            label = _label(kwargs)
            if report is not None and not isinstance(report, ExportReport):
                raise TypeError('report must be a ConversionReport')
            parent = _export_session.get()
            if parent is not None and label is None and (report is None or report is parent.report):
                return operation(*args, **kwargs)
            key = destination or kwargs.get('format')
            if key is None:
                from pathlib import Path
                path = args[1] if len(args)>1 else kwargs.get('path')
                key = Path(path).suffix if path is not None else 'unknown'
            key = key.lower().lstrip('.')
            start = len(report.notices) if report is not None else 0
            token = _export_session.set(_Session(report, key, start, file(args, kwargs), label))
            try:
                return operation(*args, **kwargs)
            except Exception as error:
                if report is not None and not any(notice.severity == 'error' for notice in report.notices[start:]):
                    report.notices.append(ConversionNotice(
                        'export-failed', key, str(error),
                        recoverability='export aborted; no complete result returned', severity='error',
                        file=file(args, kwargs), label=label))
                raise
            finally:
                _export_session.reset(token)
        return run
    return decorate


def _record(report, severity, rule, destination, message, nodes, recoverability):
    session = _export_session.get()
    if report is None and session is not None:
        report = session.report
    notice = ConversionNotice(rule, destination, message, tuple(node.path for node in nodes), recoverability, severity,
                              file=session.file if session else None, label=session.label if session else None)
    if report is not None:
        if not isinstance(report, ExportReport):
            raise TypeError('report must be a ConversionReport')
        report.notices.append(notice)
    elif severity == 'warning':
        warnings.warn(ConversionWarning(notice), stacklevel=4)
    return notice


def info(report, rule, destination, message, nodes=(), *, recoverability='equivalent destination representation'):
    """Record expected reconstruction or normalization, quietly by default."""
    return _record(report, 'info', rule, destination, message, nodes, recoverability)


def warn(report, rule, destination, message, nodes=(), *, recoverability='not preserved in destination'):
    return _record(report, 'warning', rule, destination, message, nodes, recoverability)
