"""Schematic XML font-field policy over the shared numeric projector."""
from ....common.xml_font_output import project_size as _project_size
from ....common.font_codec import PHYSICAL_XML_WIDTH_SINCE
from ....common.xml_records import application_version
from ..capabilities import XML_APPLICATION_VERSIONS


def uses_physical_width(version):
    return application_version(XML_APPLICATION_VERSIONS[version],default=PHYSICAL_XML_WIDTH_SINCE) >= PHYSICAL_XML_WIDTH_SINCE


def project_size(source, target, *, size='FontSize', legacy='FontSize',
                 floating='FontSizeFloat', mono='FontMono', version=46, attribute=True):
    return _project_size(source, target, size=size, legacy=legacy, floating=floating,
                         mono=mono, fractional=version >= 52, attribute=attribute)
