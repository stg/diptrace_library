"""Explicit path-variable choices for a detached format-format export.

Configuration is data supplied by the caller. No environment, registry,
filesystem or installed application is consulted by this adapter.
"""
from dataclasses import dataclass
import re

from .user_fields import _lowercase_mapping, label_lowercase


_VARIABLE = re.compile(r'%([^%]*)%')


def _lower(text):
    mapping = _lowercase_mapping()
    return ''.join(mapping.get(ord(character), character) for character in text)


def _length(text):
    return len(text.encode('utf-16-le', errors='surrogatepass'))//2


def _replace(text, directory, alias):
    if not directory:
        return text
    lowered, needle = _lower(text), _lower(directory)
    pieces, position = [], 0
    while (found := lowered.find(needle, position)) >= 0:
        pieces.extend((text[position:found], alias))
        position = found+len(directory)
    return ''.join((*pieces, text[position:]))


def _expand(text, environment, *, fallback=''):
    seen = set()
    while _VARIABLE.search(text):
        if text in seen or len(seen) >= 64:
            raise ValueError('cyclic or excessive path-variable expansion')
        seen.add(text)
        unresolved = False
        def substitute(match):
            nonlocal unresolved
            value = environment.get(_lower(match[1]), '')
            unresolved |= not value
            return value
        result = _VARIABLE.sub(substitute, text)
        if unresolved:
            return fallback if _length(fallback) > 5 else result
        text = result
    return text


def _valid_suffix(text):
    # Check the final nonterminal percent marker. Aliases naming a directory
    # need a separator before a remaining filename; bare directory aliases fit.
    marker = text.rfind('%', 2, len(text)-1)
    return marker < 0 or text[marker+1] in '\\/'


@dataclass(frozen=True)
class PathVariables:
    main_dir: str = ''
    program_docs: str = ''
    my_docs: str = ''
    standardlibs: bool = True
    maindir: bool = True
    programdocs: bool = True
    mydocs: bool = True
    custom: tuple = ()  # (public variable name, directory/value, enabled)

    def __post_init__(self):
        for name in ('main_dir', 'program_docs', 'my_docs'):
            if not isinstance(getattr(self, name), str):
                raise TypeError(f'{name} must be a string')
        for name in ('standardlibs', 'maindir', 'programdocs', 'mydocs'):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f'{name} must be a boolean')
        custom = tuple(tuple(row) for row in self.custom)
        if any(len(row) != 3 or not isinstance(row[0], str) or not isinstance(row[1], str)
               or not isinstance(row[2], bool) for row in custom):
            raise TypeError('custom path variables require name, value and boolean enabled')
        object.__setattr__(self, 'custom', custom)

    def select(self, variable, actual, *, project_dir='', include_project=True):
        """Choose a variable spelling while preserving the actual filename."""
        if not all(isinstance(value, str) for value in (variable, actual, project_dir)):
            raise TypeError('path spellings and project directory must be strings')
        if variable.replace(' ', '') and not actual.replace(' ', ''):
            return variable
        paths = dict(projectdir=project_dir, maindir=self.main_dir,
                     standardlibs=self.main_dir+'\\Lib' if self.main_dir else '',
                     programdocs=self.program_docs, mydocs=self.my_docs)
        enabled = {name: getattr(self, name) for name in ('standardlibs', 'maindir', 'programdocs', 'mydocs')}
        configured = {label_lowercase(name): state for name, value, state in self.custom}
        environment = dict(paths)
        environment.update((_lower(name), value) for name, value, state in self.custom if state)
        if variable.count('%') >= 2:
            for name in _VARIABLE.findall(variable):
                # The project alias is a separate format choice; the exact
                # public spelling bypasses the configurable-variable check.
                if name == 'projectdir':
                    continue
                key = label_lowercase(name)
                if name.replace(' ', '') and not enabled.get(key, configured.get(key, False)):
                    return variable
            if _expand(variable, environment) == actual:
                return variable
        candidate = _replace(actual, project_dir, '%projectdir%') if include_project else actual
        for name in ('standardlibs', 'maindir', 'programdocs', 'mydocs'):
            if name == 'mydocs' and not self.program_docs.replace(' ', ''):
                continue
            if candidate == actual and enabled[name] and paths[name].replace(' ', ''):
                candidate = _replace(candidate, paths[name], '%'+name+'%')
        for name, directory, state in self.custom:
            if not state or not name.replace(' ', '') or not directory.replace(' ', ''):
                continue
            directory = _expand(directory, environment, fallback=directory)
            trial = _replace(actual, directory, '%'+name+'%')
            if candidate == actual or candidate.count('%') >= 2 and trial != actual and _length(trial) < _length(candidate):
                candidate = trial
        return candidate if _valid_suffix(candidate) else actual


def prepare_variable_paths(schematic, choices, *, project_dir):
    """Refresh the format export path pairs on an already detached view."""
    def update(parent, variable_name, actual):
        previous = parent.scalar(variable_name, '')
        parent.set_field(variable_name, choices.select(previous, actual, project_dir=project_dir))
    for part in schematic.select('Components/Part'):
        if part.scalar('Enabled') not in (False, 'N'):
            update(part, 'LibPath_Variable', part.scalar('LibPath'))
            model = part.one('Pattern/Model3D')
            update(model, 'Model3DFile_Variable', model.scalar('Model3DFile'))
    for shape in schematic.select('Shapes/Shape'):
        if shape.scalar('Enabled') not in (False, 'N'):
            update(shape, 'Picture_File_Variable', shape.scalar('Picture_File'))
    if schematic.scalar('ProjectLibs_Type') == 2:
        for name, kind in (('ProjectLibs_Folders', 'Folder'), ('ProjectLibs_Libs', 'Lib')):
            for record in schematic.select(name+'/'+kind):
                update(record, 'VariablePath', record.values[0])
    for slot in schematic.select('CacheLib/Slots/Slot'):
        if slot.children('Definition'):
            update(slot, 'VariablePath', slot.values[1])

