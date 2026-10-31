"""PCB XML placement resources with current keys and ordered identities."""
from ....common.conversion import info, warn
from ....common.model import Element
from ....common.xml import set_attribute
from ....common.xml_output import enum_text, field, numeric
from ...model import board_rules, hierarchy_records, assembly_variants, graphic_records
from ..output_validation import check_tree


def project_layers(board, *, units):
    result = Element('CopperLayers')
    for layer in board.select('Layers/Layer'):
        check_tree(layer, board_rules.LAYER, destination='DIPXML')
        row = result.add('Lay')
        for name, value in (('Id', layer['Number']), ('Enabled', layer['Enabled']),
                            ('Locked', layer['Locked']), ('Color', layer['Color']),
                            ('Type', enum_text(layer['Type'], ('Signal', 'Plane'))),
                            ('PlanePad', enum_text(layer['HoleType'], ('By Pads', 'Fixed Ring'))),
                            ('PlaneRing', numeric(units.length(layer['HoleRing']))),
                            ('NetId', layer['NetNumber'])):
            set_attribute(row, name, value)
        field(row, 'Name', layer['Name'])
    return result


def project_vias(board, *, units, report=None):
    result = Element('ViaStyles')
    layers = board.select('Layers/Layer')
    for via in board.select('ViaStyles/ViaStyle'):
        check_tree(via, board_rules.VIA, destination='DIPXML')
        row = result.add('ViaStyle')
        first, last = (0, -1) if via['Span'] is None else (via['Lay1'], via['Lay2'])
        for name, value in (('Id', via['Id']), ('Lay1', first), ('Lay2', last),
                            ('Size', numeric(units.length(via['Size']))),
                            ('HoleSize', numeric(units.length(via['HoleSize'])))):
            set_attribute(row, name, value)
        field(row, 'Name', via['Name'])
        if via['Span'] is not None and first == 0 and last == len(layers)-1:
            info(report, 'via-full-stack-span', 'dipxml', 'XML normalizes an outer-layer span to a through via', (via,),
                 recoverability='the same current copper stack is spanned')
    return result


def project_hierarchy_sheets(board):
    result = Element('HierarchySheets')
    for sheet in board.select('HierarchySheets/HSheet'):
        check_tree(sheet, hierarchy_records.SHEET, destination='DIPXML')
        row = result.add('HSheet')
        set_attribute(row, 'Number', sheet['Number'])
        field(row, 'Name', sheet['Name'])
        updates = row.add('UpdateIds')
        for block in sheet.select('UpdateIds/UId'):
            item = updates.add('UId')
            set_attribute(item, 'Name', block['Id'])
            field(item, 'Name', block['Name'])
    return result


def project_assembly_variants(board):
    result = Element('AssemblyVariants')
    for variant in board.select('AssemblyVariants/AssemblyVariant'):
        check_tree(variant, assembly_variants.VARIANT, destination='DIPXML')
        field(result, 'AssemblyVariant', variant['Name'])
    return result


def project_groups(board, *, report=None):
    result, omitted = Element('Groups'), []
    for group in board.select('Groups/Group'):
        check_tree(group, graphic_records.GROUP, destination='DIPXML')
        row = result.add('Group')
        set_attribute(row, 'Id', group['Id'])
        if not group['Enabled']:
            set_attribute(row, 'Enabled', False)
        if group['Selected']:
            set_attribute(row, 'Selected', True)
        if group['X'] or group['Y']:
            omitted.append(group)
    if omitted:
        warn(report, 'group-attributes', 'dipxml', 'XML group records omit anchor coordinates', omitted)
    return result
