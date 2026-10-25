"""Immutable descriptions of the versions understood by format adapters."""
from dataclasses import dataclass
from .errors import UnsupportedFileError


@dataclass(frozen=True)
class FormatCapabilities:
    format: str
    family: str
    read_versions: tuple[int | str, ...]
    write_versions: tuple[int | str, ...]
    default_write_version: int | str

    def supports_read(self, version):
        return type(version) in (int, str) and version in self.read_versions

    def supports_write(self, version):
        return type(version) in (int, str) and version in self.write_versions

    def output_version(self, requested=None, *, fallback=False):
        """Choose an exact version, or an explicitly allowed earlier version.

        A different return value tells the caller to report its fallback. This
        describes adapter support, not whether a particular design loses data.
        """
        if requested is None:
            return self.default_write_version
        if self.supports_write(requested):
            return requested
        if fallback and type(requested) is int:
            earlier = [v for v in self.write_versions if type(v) is int and v < requested]
            if earlier:
                return max(earlier)
        versions = self.write_versions
        description = (f'{min(versions)} through {max(versions)}'
                       if all(type(v) is int for v in versions)
                       and tuple(range(min(versions), max(versions) + 1)) == versions else str(versions))
        raise UnsupportedFileError(f"{self.format.upper()} cannot write version {requested!r}; "
                                   f"supported output versions: {description}",
                                   format=self.format, family=self.family,
                                   version=requested, reason='version')
