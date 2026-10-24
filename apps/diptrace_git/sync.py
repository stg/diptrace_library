"""Synchronize design pairs without replacing unchanged original binaries."""
from contextlib import contextmanager
from dataclasses import dataclass, field
import os

from lib import ConversionNotice, ConversionReport, format_capabilities, parse, serialize

from .config import METADATA_SUFFIX, companions, load_config, load_manifest, manifest
from .files import atomic_write, digest, json_bytes, read_json, snapshot, unchanged


@dataclass
class Result:
    actions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notices: list[ConversionNotice] = field(default_factory=list)
    staged: set[str] = field(default_factory=set)
    pending: list[str] = field(default_factory=list)


@contextmanager
def locked(repo):
    repo.state_dir.mkdir(parents=True, exist_ok=True)
    lock = repo.state_dir / 'sync.lock'
    try:
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError(f'conversion is already running ({lock}); if it was interrupted, '
                         'remove this lock only after confirming that process has stopped') from None
    try:
        os.close(handle)
        yield
    finally:
        lock.unlink()


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
            if not isinstance(entry.get('instructions'), list):
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


def discover(repo, config):
    manifests = repo.names('ls-files', '--cached', '--others', '--exclude-standard', '--',
                           ':(icase)*.dch' + METADATA_SUFFIX)
    binaries = repo.names('ls-files', '--cached', '--others', '--', ':(icase)*.dch')
    selected = repo.selected(binaries | {name[:-len(METADATA_SUFFIX)] for name in manifests}, config['rules'])
    return [(binary, load_manifest(repo, binary + METADATA_SUFFIX)
             if binary + METADATA_SUFFIX in manifests else None)
            for binary in sorted(selected)]


def synchronize(repo, *, direction='auto', force=False, stage=False, untrack=False,
                verify=False, dry_run=False, files=None):
    if force and direction == 'auto':
        raise ValueError('--force needs export or rebuild to choose which side wins')
    config = load_config(repo)
    result = Result()
    with locked(repo), saved_state(repo, dry_run) as state:
        tracked = repo.names('ls-files', '--cached')
        unmerged = repo.names('diff', '--name-only', '--diff-filter=U')
        staged_changes = repo.names('diff', '--cached', '--name-only')
        unstaged_changes = repo.names('diff', '--name-only')
        deleted = repo.names('diff', '--cached', '--name-only', '--diff-filter=D')
        entries = discover(repo, config)
        owners = {}
        for binary, metadata in entries:
            text_format = metadata['text']['path'].rsplit('.', 1)[1] if metadata else config['text_format']
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
                text_format = metadata['text']['path'].rsplit('.', 1)[1] if metadata else config['text_format']
                names = {binary, *companions(binary, text_format)}
                if names & requested:
                    matched.append((binary, metadata))
                    requested -= names
            if requested:
                raise ValueError('not selected by the current rules: ' + ', '.join(sorted(requested)))
            entries = matched
        for binary, metadata in entries:
            text_format = (metadata['text']['path'].rsplit('.', 1)[1]
                           if metadata else config['text_format'])
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
            if previous and previous['instructions'] != instructions:
                if not force:
                    raise ValueError(f'{binary}: reconstruction settings changed; choose '
                                     'export --force or rebuild --force explicitly')
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
            report = ConversionReport()
            generated = None
            binary_design = None

            def export_binary(*, refresh_version=False):
                nonlocal binary_design, metadata, generated
                if b is None:
                    raise ValueError(f'{binary}: binary is missing')
                binary_design = parse(b.data if b.data is not None else binary_path.read_bytes(),
                                      format='dch', report=report, label=binary)
                if metadata is None or refresh_version:
                    metadata = manifest(binary, binary_design.metadata['source_version'], text_format)
                version = output_version()
                options = {'version': version} if text_format == 'dchxml' else {}
                generated = serialize(binary_design, format=text_format, report=report,
                                      label=text, **options)
                return generated

            def output_version():
                requested = metadata['binary']['version']
                chosen = format_capabilities('dch').output_version(
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
            if action == 'binary':
                updates[text] = export_binary(refresh_version=True)
                result.actions.append(f'export {binary} -> {text}')
            elif action == 'text':
                if t is None or metadata is None:
                    raise ValueError(f'{binary}: text and reconstruction metadata are required')
                design = parse(t.data if t.data is not None else text_path.read_bytes(),
                               format=text_format, report=report, label=text)
                updates[binary] = serialize(design, format='dch', version=output_version(),
                                            report=report, label=binary)
                result.actions.append(f'rebuild {text} -> {binary}')
            elif action == 'adopt':
                result.actions.append(f'verify {binary} (original preserved)')

            if metadata is not None and (meta_before is None or action == 'binary'):
                updates[meta_name] = json_bytes(metadata)
            result.notices.extend(report.notices)
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
                continue
            for name, data in updates.items():
                atomic_write(repo.path(name), data)
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
