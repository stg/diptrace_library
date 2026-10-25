"""Public failures shared by document families and format adapters."""


class UnsupportedFileError(ValueError):
    """Unsupported format, document family or version, with available identity."""

    def __init__(self, message='unsupported file format', *, format=None,
                 family=None, version=None, reason='format'):
        if reason not in ('format', 'family', 'version'):
            raise ValueError('unsupported-file reason must be format, family or version')
        super().__init__(message)
        self.format = format
        self.family = family
        self.version = version
        self.reason = reason
