"""Prepare XML document preferences before the PCB identity assembly."""
from ....common.xml_library_values import read_project_libraries
from .versions import XmlVersion
from .settings import read_settings, read_connectivity
from .panel import read_panel
from .sheet import read_sheet
from .hierarchy import read_sheets
from .project_options import PROJECT_LIBRARY_DEFAULTS


def read_document_settings(record, root, board, *, units, application_version):
    version = XmlVersion.parse(application_version)
    read_panel(record.take('Panel'), board, units=units, version=version)
    read_sheet(record.take('SheetSettings'), root, board, units=units)
    read_settings(record.take('Settings'), board, units=units)
    read_connectivity(record.take('ConnectivityCheck'), board)
    projects = record.take('ProjectLibs')
    if projects is not None:
        for name, value in PROJECT_LIBRARY_DEFAULTS.items():
            board.add(name, value)
    read_project_libraries(projects, board)
    read_sheets(record.take('HierarchySheets'), board)
