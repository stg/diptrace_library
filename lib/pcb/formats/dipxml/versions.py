"""XML compatibility conventions shared by import and destination projection."""
from dataclasses import dataclass
from ....common.font_codec import PHYSICAL_XML_WIDTH_SINCE
from ....common.xml_records import application_version

from ..errors import PcbError
from ..capabilities import DIPXML, XML_APPLICATION_VERSIONS


CURRENT_APPLICATION = tuple(map(int, XML_APPLICATION_VERSIONS[DIPXML.default_write_version].split('.')))


@dataclass(frozen=True)
class XmlVersion:
    application: tuple[int, int, int, int]

    @classmethod
    def output(cls, version=None):
        selected = DIPXML.output_version(version)
        return cls(tuple(map(int, XML_APPLICATION_VERSIONS[selected].split('.'))))

    @property
    def application_text(self):
        return '.'.join(map(str, self.application))

    @property
    def current_fields(self):
        """Fractional fonts, explicit pad inheritance and newer board options."""
        return self.application >= (5, 3, 5, 0)

    @classmethod
    def parse(cls, text):
        try:
            return cls(application_version(text,default=CURRENT_APPLICATION))
        except ValueError:
            raise PcbError(f'invalid PCB XML application version {text.strip()!r}') from None

    @property
    def legacy_panel_coordinates(self):
        return self.application <= (4, 3, 0, 3)

    @property
    def legacy_table_pickoff_y(self):
        return self.application <= (4, 3, 0, 3)

    @property
    def legacy_cell_line_spacing(self):
        return self.application < (5, 3, 5, 0)

    @property
    def panel_metrics_in_display_units(self):
        return self.application >= (5, 3, 5, 0)

    @property
    def routing_metrics_in_display_units(self):
        """Separate-trace widths and ordinary phase lengths changed together."""
        return self.application >= (5, 3, 5, 0)

    @property
    def physical_pour_area(self):
        return self.application > (4, 3, 0, 3)

    @property
    def physical_dimension_arrow(self):
        return self.application > (4, 3, 0, 3)

    @property
    def physical_font_width(self):
        return self.application >= PHYSICAL_XML_WIDTH_SINCE

    @property
    def drc_copper_pours_name(self):
        return 'CheckCoperPours' if self.application <= (4, 3, 0, 3) else 'CheckCopperPours'
