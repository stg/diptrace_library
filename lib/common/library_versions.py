"""Application-version features shared by standalone library output profiles."""
from dataclasses import dataclass, replace

from .errors import UnsupportedFileError
from .font_codec import PHYSICAL_XML_WIDTH_SINCE
from .xml_records import application_version


def library_text_layout(*, current=True):
    """Shared calculation defaults; no input-document provenance is retained."""
    from .text.layout import default_layout
    from .text.vector import builtin_vector_metrics
    metrics = builtin_vector_metrics()
    if current:
        metrics = replace(metrics, line_height=1.618)
    return default_layout(vector_metrics=metrics)


@dataclass(frozen=True)
class LibraryApplicationVersion:
    application: tuple

    @classmethod
    def select(cls, version, *, family, format, applications):
        selected = applications[-1] if version is None else version
        if selected not in applications:
            raise UnsupportedFileError(family=family, format=format, version=selected, reason='version')
        return cls(application_version(selected, default=(5, 3, 5, 1)))

    @property
    def text(self):
        return '.'.join(map(str, self.application))

    @property
    def current_fields(self):
        return self.application >= (5, 3, 5, 0)

    @property
    def drawing_pad_links(self):
        return self.application >= (4, 9, 5, 0)

    @property
    def physical_font_width(self):
        return self.application >= PHYSICAL_XML_WIDTH_SINCE

    def text_layout(self):
        """Layout defaults for this receiver, with independently measured metrics.

        Single/multiline text fixtures distinguish the current vector font's
        taller rows from the earlier profile without changing glyph advances.
        This changes calculated boxes, never authored anchors or font sizes.
        """
        return library_text_layout(current=self.current_fields)
