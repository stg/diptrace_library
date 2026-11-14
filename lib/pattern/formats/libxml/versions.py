"""Declared standalone pattern XML destinations."""
from ....common.library_versions import LibraryApplicationVersion
from ..revisions import APPLICATION_VERSIONS as APPLICATIONS


class XmlVersion(LibraryApplicationVersion):
    @classmethod
    def output(cls, version=None):
        return cls.select(version, family='pattern', format='libxml', applications=APPLICATIONS)
