"""Synchronize design pairs without replacing unchanged original binaries."""
from contextlib import contextmanager
from dataclasses import dataclass, field
import os

from lib import ConversionNotice, ConversionReport, UnsupportedFileError, format_capabilities, input_identity, parse, serialize

from .config import FAMILIES, METADATA_SUFFIX, companion_format, companions, load_config, load_manifest, manifest, native_format, serialization
from .files import atomic_write, digest, json_bytes, read_json, snapshot, unchanged
from .locking import internal_commands, locked


@dataclass
class Result:
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notices: list[ConversionNotice] = field(default_factory=list)
    staged: set[str] = field(default_factory=set)
    pending: list[str] = field(default_factory=list)


def load_state(repo):
    try:
        state = read_json(repo.state_dir / 'state.json')
        if state.get('version') != 1 or state.get('root') != str(repo.root):
            return {}
        entries = state['files']
        if not isinstance(entries, dict):
            return {}
        # A cache is disposable, never authority for overwriting a design. An
        # incomplete entry must fall back to safe pair verification.
        for entry in entries.values():
            instructions = entry.get('instructions')
            if (not isinstance(instructions, list) or len(instructions) != 3
                    or not all(isinstance(v, str) for v in instructions[:2])
                    or type(instructions[2]) is not int):
                return {}
            generated = entry.get('generated', {})
            if not isinstance(generated, dict) or not all(isinstance(k, str) and isinstance(v, str)
                                                          for k, v in generated.items()):
                return {}
            for kind in ('binary', 'text'):
                item = entry[kind]
                if (not isinstance(item['sha256'], str) or len(item['sha256']) != 64
                        or set(item['stamp']) != {'mtime_ns', 'ctime_ns', 'size'}
                        or not all(type(v) is int for v in item['stamp'].values())):
                    return {}
        return entries
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


@contextmanager
def saved_state(repo, dry_run):
    """Save once per batch, including completed pairs before a later failure."""
    state = load_state(repo)
    initial = json_bytes(state)
    try:
        yield state
    finally:
        if not dry_run and json_bytes(state) != initial:
            atomic_write(repo.state_dir / 'state.json', json_bytes(
                {'version': 1, 'root': str(repo.root), 'files': state}))


def candidates(repo):
    patterns = [':(icase)*.' + key for key in FAMILIES]
    manifests = repo.names('ls-files', '--cached', '--others', '--exclude-standard', '--',
                           *(p + METADATA_SUFFIX for p in patterns))
    binaries = repo.names('ls-files', '--cached', '--others', '--', *patterns)
    return binaries | {name[:-len(METADATA_SUFFIX)] for name in manifests}


def discover(repo, config, pending=None, *, include_deleted=False):
    selected = repo.selected(candidates(repo), config['rules'])
    unmerged = repo.names('diff', '--name-only', '--diff-filter=U')
    previous = load_state(repo)
    entries = []
    for binary in sorted(selected):
        meta = binary + METADATA_SUFFIX
        possible = {binary, meta, *companions(binary, 'asc'), *companions(binary, 'xml')}
        if possible & unmerged:
            if pending is not None:
                pending.append(f'{binary}: resolve Git conflicts; the native file is unchanged')
            continue
        if not repo.path(meta).exists() and binary in previous and not include_deleted:
            if repo.path(previous[binary]['instructions'][1]).exists():
                raise ValueError(f'{meta}: missing reconstruction settings; restore from Git, '
                                 'use export --force, or disable the design')
            continue  # A Git deletion must not recreate artifacts from an ignored original.
        entries.append((binary, load_manifest(repo, meta) if repo.path(meta).exists() else None))
    return entries


def index_hash(repo, name, *, text=False):
    rows = repo.run('ls-files', '--stage', '-z', '--', ':(literal)' + name).split(b'\0')
    if len(rows) == 2 and rows[0].split(b'\t', 1)[0].endswith(b' 0'):
        oid = rows[0].split()[1].decode('ascii')
        return digest(repo.run('cat-file', 'blob', oid), text=text)
    return None


def error_message(error):
    if isinstance(error, UnsupportedFileError):
        identity = ' '.join(str(v) for v in (error.family, error.format, error.version) if v is not None)
        return identity + ': ' + str(error)
    return str(error)


def invalidate(repo):
    names = {entry['instructions'][1] for entry in load_state(repo).values()}
    names |= repo.names('ls-files', '--cached', '--', '*.git.asc', '*.git.xml', '*.git.json')
    for name in names:
        try:
            path = repo.path(name)
            if path.is_file():
                stat = path.stat()
                os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
        except (OSError, ValueError):
            pass  # Keep the processing error which caused invalidation.


def synchronize(repo, *, direction='auto', force=False, stage=False, untrack=False,
                verify=False, dry_run=False, files=None, installed=False, require_installation=False):
    with internal_commands(), locked(repo):
        if require_installation:
            installation = repo.common_dir / 'diptrace-git/installation.json'
            if not installation.exists():
                return Result()
            if read_json(installation).get('pending'):
                raise ValueError('installation is incomplete; rerun init or uninstall before using the integration')
        error_path = repo.state_dir / 'hook-error.json'
        result = Result()
        try:
            result = _synchronize(repo, direction=direction, force=force, stage=stage,
                                  untrack=untrack, verify=verify, dry_run=dry_run,
                                  files=files, installed=installed, result=result)
            if not dry_run:
                from .setup import refresh_ignore
                refresh_ignore(repo)
                if error_path.exists():
                    error_path.unlink()
            return result
        except (OSError, ValueError, TypeError, LookupError, NotImplementedError) as error:
            error.diptrace_result = result
            if not dry_run:
                atomic_write(error_path, json_bytes({'message': error_message(error)}))
                invalidate(repo)
            raise


def _synchronize(repo, *, direction='auto', force=False, stage=False, untrack=False,
                verify=False, dry_run=False, files=None, installed=False, result=None):
    if force and direction == 'auto':
        raise ValueError('--force needs export or rebuild to choose which side wins')
    config = load_config(repo)
    if result is None:
        result = Result()
    with saved_state(repo, dry_run) as state:
        tracked = repo.names('ls-files', '--cached')
        unmerged = repo.names('diff', '--name-only', '--diff-filter=U')
        staged_changes = repo.names('diff', '--cached', '--name-only')
        unstaged_changes = repo.names('diff', '--name-only')
        deleted = repo.names('diff', '--cached', '--name-only', '--diff-filter=D')
        entries = discover(repo, config, result.pending,
                           include_deleted=force and direction == 'binary' and bool(files))
        flags = repo.run('ls-files', '-v', '-z').split(b'\0')
        artifacts = {name for binary, metadata in entries for name in
                     companions(binary, companion_format(metadata) if metadata else config['text_format'])}
        for row in flags:
            if row and os.fsdecode(row[2:]) in artifacts and (chr(row[0]).islower() or chr(row[0]) == 'S'):
                raise ValueError('managed artifacts cannot use assume-unchanged or skip-worktree; '
                                 'clear the Git flag or disable that design')
        owners = {}
        for binary, metadata in entries:
            text_format = companion_format(metadata) if metadata else serialization(binary, config['text_format'])
            for name in (binary, *companions(binary, text_format)):
                path = repo.path(name).resolve()
                if path in owners and owners[path] != binary:
                    raise ValueError(f'{binary} and {owners[path]} would share output {name}')
                owners[path] = binary
        if files:
            requested = {repo.path(str(name).replace('\\', '/')).resolve().relative_to(repo.root).as_posix()
                         for name in files}
            matched = []
            for binary, metadata in entries:
                text_format = companion_format(metadata) if metadata else serialization(binary, config['text_format'])
                names = {binary, *companions(binary, text_format)}
                if names & requested:
                    matched.append((binary, metadata))
                    requested -= names
            if requested:
                raise ValueError('not selected by the current rules: ' + ', '.join(sorted(requested)))
            entries = matched
        for binary, metadata in entries:
            text_format = (companion_format(metadata)
                           if metadata else serialization(binary, config['text_format']))
            text, meta_name = companions(binary, text_format)
            if {text, meta_name} & unmerged:
                raise ValueError(f'{binary}: resolve Git conflicts in its companions first')
            if metadata is None and (text in deleted or meta_name in deleted or direction == 'text'):
                continue
            if binary in tracked and not untrack:
                raise ValueError(f'{binary} is already tracked; run sync --untrack to migrate it '
                                 'without deleting the working binary')
            paths = [repo.path(name) for name in (binary, text, meta_name)]
            binary_path, text_path, meta_path = paths
            previous = state.get(binary)
            instructions = [binary, text, metadata['binary']['version']] if metadata else None
            settings_changed = bool(previous and previous['instructions'] != instructions)
            if force:
                previous = None
            b = snapshot(binary_path, previous['binary'] if previous else None, verify=verify)
            t = snapshot(text_path, previous['text'] if previous else None, text=True, verify=verify)
            meta_before = snapshot(meta_path)
            if b is None and t is None:
                raise ValueError(f'{binary}: both binary and text companion are missing')
            if metadata is not None and t is None and not (force and direction == 'binary'):
                raise ValueError(f'{text}: missing companion; use export --force to recreate it')

            b_changed = b is not None and (not previous or b.sha256 != previous['binary']['sha256'])
            t_changed = t is not None and (not previous or t.sha256 != previous['text']['sha256'])
            native = native_format(binary)
            family = FAMILIES[native]
            capabilities = format_capabilities(native, family=family)
            format_capabilities(text_format, family=family)
            integrating = installed or any(repo.git_path(name).exists() for name in
                ('rebase-merge', 'rebase-apply', 'MERGE_HEAD', 'CHERRY_PICK_HEAD'))
            if settings_changed and not force:
                if b_changed:
                    raise ValueError(f'{binary}: reconstruction settings conflict with native edits')
                if not integrating and index_hash(repo, meta_name) != meta_before.sha256:
                    raise ValueError(f'{meta_name}: generated reconstruction settings were edited; '
                                     'restore them from Git or explicitly rebuild --force')
            if (previous and t_changed and not b_changed and not force and not integrating
                    and index_hash(repo, text, text=True) != t.sha256):
                raise ValueError(f'{text}: generated companion was edited; regenerate with export --force '
                                 'or explicitly accept it with rebuild --force')
            report = ConversionReport(result.notices)
            generated = None
            binary_design = None

            def export_binary(*, refresh_version=False):
                nonlocal binary_design, metadata, generated
                if b is None:
                    raise ValueError(f'{binary}: binary is missing')
                data = b.data if b.data is not None else binary_path.read_bytes()
                binary_design = parse(data, family=family, report=report, label=binary)
                if metadata is None or refresh_version:
                    metadata = manifest(binary, input_identity(data).version, text_format)
                version = output_version()
                text_capabilities = format_capabilities(text_format, family=family)
                options = ({'version': version} if text_format.endswith('xml')
                           and text_capabilities.supports_write(version) else {})
                generated = serialize(binary_design, format=text_format, family=family, report=report,
                                      label=text, **options)
                return generated

            def output_version():
                requested = metadata['binary']['version']
                chosen = capabilities.output_version(
                    requested, fallback=config.get('fallback_earlier', False))
                if requested != chosen:
                    message = f'{binary}: schema {requested} cannot be written; using earlier schema {chosen}'
                    if message not in result.warnings:
                        result.warnings.append(message)
                return chosen

            # No local cache is not evidence that either side is newer. Recreate
            # text in memory to prove an existing pair agrees, leaving the
            # original DCH entirely untouched. Otherwise require a direction.
            adopted = False
            if previous is None and b is not None and t is not None and not force:
                adopted = digest(export_binary(), text=True) == t.sha256
                if not adopted:
                    raise ValueError(f'{binary}: no synchronization baseline and companions differ; '
                                     'choose export --force or rebuild --force')
            if force:
                action = direction
            elif settings_changed:
                action = 'text'
            elif adopted:
                action = 'adopt'
            elif b is None:
                action = 'text'
            elif t is None:
                action = 'binary'
            elif b_changed and t_changed:
                raise ValueError(f'{binary}: both binary and text changed; choose '
                                 'export --force or rebuild --force after reviewing them')
            elif b_changed:
                action = 'binary' if direction != 'text' else 'skip'
            elif t_changed:
                action = 'text' if direction != 'binary' else 'skip'
            else:
                action = 'skip'

            updates = {}
            message = None
            if action == 'binary':
                updates[text] = export_binary(refresh_version=True)
                message = f'export {binary} -> {text}'
            elif action == 'text':
                if t is None or metadata is None:
                    raise ValueError(f'{binary}: text and reconstruction metadata are required')
                design = parse(t.data if t.data is not None else text_path.read_bytes(),
                               format=text_format, family=family, report=report, label=text)
                updates[binary] = serialize(design, format=native, family=family, version=output_version(),
                                            report=report, label=binary)
                message = f'rebuild {text} -> {binary}'
            elif action == 'adopt':
                message = f'verify {binary} (original preserved)'

            if metadata is not None and (meta_before is None or action == 'binary'):
                updates[meta_name] = json_bytes(metadata)
            current = {binary: b, text: t, meta_name: meta_before}
            updates = {name: data for name, data in updates.items()
                       if current[name] is None or
                       current[name].sha256 != digest(data, text=name == text)}
            # Updating a generated file must not replace a partially staged
            # snapshot. Only generated companions are automatically added.
            if stage and set(updates) & staged_changes:
                raise ValueError(f'{binary}: a generated update would replace a staged companion; '
                                 'review and unstage it before synchronization replaces that snapshot')
            for path, before in zip(paths, (b, t, meta_before)):
                if not unchanged(path, before):
                    raise ValueError(f'{path}: changed during conversion; try again')
            if dry_run:
                if message is not None:
                    result.actions.append(message)
                continue
            for name, data in updates.items():
                atomic_write(repo.path(name), data)
            if message is not None:
                result.actions.append(message)
            if untrack and binary in tracked:
                repo.run('rm', '--cached', '--', ':(literal)' + binary)
                result.actions.append(f'untrack {binary} (working file preserved)')
            # A skipped change in the other direction is still unsynchronized;
            # never bless it as the next baseline.
            if action == 'skip' and (b_changed or t_changed):
                result.pending.append(f'{binary}: local edits kept; run ' +
                                      ('export' if b_changed else 'rebuild') + ' to synchronize them')
                continue
            b_final = snapshot(binary_path, b.saved() if b and binary not in updates else None)
            t_final = snapshot(text_path, t.saved() if t and text not in updates else None, text=True)
            m_final = snapshot(meta_path, meta_before.saved() if meta_before and meta_name not in updates else None)
            generated_files = dict(previous.get('generated', {})) if previous else {}
            if action == 'text':
                generated_files.pop(text, None)  # Direct text edits retain ordinary Git staging semantics.
            for name, data in updates.items():
                if name != binary:
                    generated_files[name] = digest(data, text=name == text)
            state[binary] = {'instructions': [binary, text, metadata['binary']['version']],
                             'binary': b_final.saved(), 'text': t_final.saved(),
                             'generated': generated_files}
            if stage:
                current = {text: t_final.sha256, meta_name: m_final.sha256}
                to_stage = {name for name, sha in generated_files.items()
                            if current.get(name) == sha and
                            (name not in tracked or name in unstaged_changes or name in updates)}
                if to_stage & staged_changes & unstaged_changes:
                    raise ValueError(f'{binary}: companion has staged and unstaged edits; '
                                     'resolve its partial staging before synchronization')
                repo.stage(to_stage)
                result.staged.update(to_stage)
    return result
