"""Public footprint parameters and authoring labels shared by XML adapters."""
from .xml import set_attribute
from .xml_output import enum_text, field, numeric, point_attributes
from .xml_library_output import project_category
from .xml_plan import XmlBuilder


def project_pattern_header(pattern, result, *, units, type_label, include_empty_templates=False):
    """Emit template facts; each family selects its allowed type and defaults."""
    set_attribute(result,'Type',type_label)
    set_attribute(result,'Mounting',enum_text(pattern['Mounting'],('Through','SMD','Chassis','Mixed'),negative='None'))
    orientation = pattern['PatternOrientation']
    set_attribute(result,'Orientation',orientation*90 if orientation in (0,1,2,3) else orientation)
    set_attribute(result,'LockTypeChange',pattern['LockProperties'])
    for name in ('Width','Height'):
        set_attribute(result,name,numeric(units.length(pattern._field_arguments(name)[0])))
    for index in (1,2,3):
        set_attribute(result,'Float'+str(index),numeric(units.length(pattern._field_arguments('Spacing'+str(index))[0])))
    for index in (1,2):
        set_attribute(result,'Int'+str(index),pattern['Number'+str(index)])
    field(result,'Name',pattern['Name'])
    if pattern.get('RefDes','') or include_empty_templates and pattern.child('RefDes') is not None:
        set_attribute(result,'RefDes',pattern['RefDes'])
    for public, own in (('Value','Value'),('Name_Description','Name_Description'),('Name_Unique','Name_Unique'),
                        ('Datasheet','Datasheet'),('Manufacturer','Pattern_Manufacturer')):
        if pattern.get(own,'') or include_empty_templates and own == 'Value' and pattern.child(own) is not None:
            field(result,public,pattern[own])
    if category := project_category(pattern, _factory=XmlBuilder):
        result.append(category)
    names = pattern.select('PossibleNames/PossibleName')
    if names:
        target = result.add('PossibleNames')
        for name in names:
            field(target,'PossibleName',name['Name'])
    origin = result.add('Origin')
    point_attributes(origin,pattern['OriginX'],pattern['OriginY'],units)
    for public, own in (('Cross','OriginCross'),('Circle','OriginCircle')):
        set_attribute(origin,public,pattern[own])
    set_attribute(origin,'Common',enum_text(pattern['OriginCommon'],('Show','Hide')))
    set_attribute(origin,'Courtyard',enum_text(pattern['OriginCourtyard'],('Show','Hide','Show if not center')))
    if pattern['RecoveryCode'] or not all(pattern['RecoveryCode_'+name] for name in ('Generator', 'Model')):
        target = field(result,'RecoveryCode',pattern['RecoveryCode'])
        for name in ('Generator','Model'):
            set_attribute(target,name,pattern['RecoveryCode_'+name])


def project_pattern_user_fields(pattern, result):
    users = pattern.select('UserFields/UserField')
    if users:
        target = result.add('AddFields')
        for user in users:
            row = target.add('AddField')
            set_attribute(row,'Type',enum_text(user['Type'],('Text','Link')))
            field(row,'Name',user['Name'])
            field(row,'Text',user['Value'])
