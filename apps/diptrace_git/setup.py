"""Reversible local Git integration and explicit pathspec selection."""
from pathlib import Path, PurePosixPath
import re
import shlex
import sys

from .config import (CONFIG, ConfigurationError, LEGACY, SIGNATURE, companions, load_config,
                     new_config, validate_pathspec)
from .files import atomic_write, json_bytes, read_json
from .locking import internal_commands, locked

START = '# BEGIN diptrace-git'
END = '# END diptrace-git'
HOOKS = ('pre-commit', 'post-checkout', 'post-merge', 'post-rewrite', 'post-index-change')
DRIVER = 'diptrace'


def marked_file(repo, filename, rules):
    """Only replace our marked block; retain unrelated ignore entries verbatim."""
    path = repo.path(filename)
    original = path.read_bytes() if path.exists() else b''
    lines = original.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip(b'\r\n') == START.encode()]
    ends = [i for i, line in enumerate(lines) if line.rstrip(b'\r\n') == END.encode()]
    if len(starts) != len(ends) or len(starts) > 1 or starts and starts[0] > ends[0]:
        raise ValueError(f'{filename} has an incomplete diptrace-git block; repair its markers first')
    newline = b'\r\n' if b'\r\n' in original else b'\n'
    block = newline.join(line.encode('utf-8') for line in (START, *rules, END)) + newline if rules else b''
    if starts:
        updated = b''.join(lines[:starts[0]]) + block + b''.join(lines[ends[0] + 1:])
    elif block:
        updated = original + (newline if original and not original.endswith(b'\n') else b'') + block
    else:
        return
    atomic_write(path, updated)



def ignore_rules(repo, rules):
    marked_file(repo, '.gitignore', rules)


def ignore_literal(name):
    return '/' + ''.join('\\' + c if c in '*?[]!# \\' else c for c in name)


def refresh_ignore(repo):
    from .sync import candidates
    config = load_config(repo)
    selected = repo.selected(candidates(repo), config['rules'])
    ignore_rules(repo, [ignore_literal(name) for name in sorted(selected)])


def change_selection(repo, patterns, *, enabled):
    from .sync import candidates, load_state
    for pattern in patterns:
        validate_pathspec(pattern)
    with internal_commands(), locked(repo):
        config = load_config(repo)
        rule = {'pathspecs': list(patterns), 'enabled': enabled}
        names = candidates(repo)
        repo.selected(names or {'.diptrace-validation.dch'}, [rule])  # Validate magic even before files exist.
        config['rules'].append(rule)
        atomic_write(repo.path(CONFIG), json_bytes(config))
        if enabled:
            state = load_state(repo)
            for name in repo.selected(names, [rule]):
                if not repo.path(name + '.git.json').exists():
                    state.pop(name, None)  # Explicit re-enrollment after deleting artifacts.
            atomic_write(repo.state_dir / 'state.json', json_bytes(
                {'version': 1, 'root': str(repo.root), 'files': state}))
        refresh_ignore(repo)


def migrate(repo):
    """Move only metadata-proven legacy artifacts; keep native bytes and history."""
    from .sync import candidates
    path = repo.path(CONFIG)
    config = read_json(path)
    if config.get('format') != LEGACY:
        return None
    if (config.get('text_format') not in ('asc', 'dchxml')
            or not isinstance(config.get('rules'), list)
            or not all(isinstance(rule, str) for rule in config['rules'])
            or type(config.get('fallback_earlier', False)) is not bool):
        raise ConfigurationError('invalid legacy .diptrace-git.json; review its text_format, rules and fallback_earlier')
    names = candidates(repo)
    selected = repo.legacy_selected(names, config['rules'])
    changed = repo.names('diff', '--name-only') | repo.names('diff', '--cached', '--name-only')
    plan = []
    for binary in sorted(selected):
        meta = binary + '.git.json'
        if not repo.path(meta).exists():
            continue
        value = read_json(repo.path(meta))
        try:
            source = value['text']['path']
            fmt = PurePosixPath(source).suffix.lstrip('.')
            if (value['format'] != LEGACY or value['binary']['path'] != binary
                    or type(value['binary']['version']) is not int or fmt not in ('asc', 'dchxml')
                    or source != str(PurePosixPath(binary).with_suffix('.' + fmt))):
                raise ValueError(f'{meta}: invalid legacy reconstruction metadata')
            if {source, meta} & changed:
                raise ValueError('commit or resolve legacy artifact edits before migrating')
            src = repo.path(source)
            destination = repo.path(companions(binary, fmt)[0])
            data = src.read_bytes()
            if destination.exists():
                raise ValueError(f'migration destination exists: {destination.name}')
            value['format'] = SIGNATURE
            value['text']['path'] = destination.relative_to(repo.root).as_posix()
            plan.append((src, destination, data, repo.path(meta), json_bytes(value)))
        except (KeyError, TypeError):
            raise ValueError(f'{meta}: invalid legacy metadata') from None
    replacement = new_config(config['text_format'], config.get('fallback_earlier', False))
    replacement['rules'] = [{'pathspecs': [':(top,literal)' + n for n in sorted(selected)], 'enabled': True}] if selected else []
    # Every path and collision is checked before the first mutation. Git retains
    # the previous files; no native file or historical object is changed.
    for src, dest, data, meta, metadata in plan:
        atomic_write(dest, data)
        atomic_write(meta, metadata)
        src.unlink()
    atomic_write(path, json_bytes(replacement))
    cache = repo.state_dir / 'state.json'
    if cache.exists():
        cache.unlink()
    return 'Migrated existing selected designs. Use enable pathspecs to include future files.'


def install(repo, *, text_format=None, fallback=None, migrate_legacy=False):
    with internal_commands(), locked(repo):
        return _install(repo, text_format=text_format, fallback=fallback, migrate_legacy=migrate_legacy)


def _install(repo, *, text_format=None, fallback=None, migrate_legacy=False):
    version = re.search(r'(\d+)\.(\d+)', repo.run('--version').decode())
    if version is None or tuple(map(int, version.groups())) < (2, 26):
        raise ValueError('diptrace-git requires Git 2.26 or newer for fsmonitor protocol 2')
    home = repo.common_dir / 'diptrace-git'
    record_path = home / 'installation.json'
    hooks, runner = home / 'hooks', home / 'runner.py'
    prefix = ' '.join(shlex.quote(v) for v in (Path(sys.executable).as_posix(), runner.resolve().as_posix()))
    installed = {'core.hooksPath': hooks.resolve().as_posix(), 'alias.diptrace': '!' + prefix,
                 'core.fsmonitor': prefix + ' monitor', 'core.fsmonitorHookVersion': '2',
                 'filter.diptrace.clean': prefix + ' filter clean -- %f',
                 'filter.diptrace.smudge': prefix + ' filter smudge -- %f',
                 'filter.diptrace.required': 'true'}
    worktree_config = repo.git_path('config.worktree')
    if (worktree_config.exists() and repo.run('config', '--bool', '--get',
            'extensions.worktreeConfig', check=False).strip() == b'true'):
        for key in installed:
            if repo.run('config', '--file', str(worktree_config), '--includes', '--get', key, check=False):
                raise ValueError(f'{key} has a per-worktree override; reconcile it before init '
                                 '(the integration uses common local Git settings)')
    if record_path.exists():
        record = read_json(record_path)
        prior_installed = record.get('installed', {'core.hooksPath': installed['core.hooksPath'],
                                                  'alias.diptrace': record['installed_alias']})
        for key, value in prior_installed.items():
            allowed = record.get('resume_values', {}).get(key, [value]) if record.get('pending') else [value]
            if repo.config(key) not in allowed:
                raise ValueError(f'{key} changed since installation; resolve it before reinstalling')
        for key in installed:
            if key.startswith('filter.') and key not in prior_installed and repo.config(key) is not None:
                raise ValueError('filter.diptrace already exists; preserve or rename that driver before upgrading')
    else:
        if repo.config('alias.diptrace') is not None:
            raise ValueError('alias.diptrace already exists; choose another alias before init')
        if repo.config('core.hooksPath') == hooks.resolve().as_posix():
            raise ValueError('installation record is missing; restore core.hooksPath before init')
        record = {'previous_local_hooks_path': repo.config('core.hooksPath', local=True),
                  'previous_hooks_path': repo.config('core.hooksPath', path=True)
                    or (repo.common_dir / 'hooks').resolve().as_posix()}
        if any(repo.config(key) is not None for key in installed if key.startswith('filter.')):
            raise ValueError('filter.diptrace already exists; preserve or rename that driver before init')
    monitor = repo.config('core.fsmonitor')
    if monitor not in (None, '', 'false', '0', installed['core.fsmonitor']):
        raise ValueError('core.fsmonitor is already configured; diptrace-git cannot share that monitor. '
                         'Keep the existing integration or explicitly disable it before init')
    config_path = repo.path(CONFIG)
    if config_path.exists() and read_json(config_path).get('format') == LEGACY and not migrate_legacy:
        raise ValueError('legacy configuration; use init --migrate to migrate existing selected designs')
    # Check marked files before changing config or local settings.
    for name in ('.gitignore', '.gitattributes'):
        existing = repo.path(name).read_bytes() if repo.path(name).exists() else b''
        start, end = START.encode(), END.encode()
        if existing.count(start) != existing.count(end) or existing.count(start) > 1:
            raise ValueError(f'{name}: incomplete managed block')
        if start in existing and existing.index(start) > existing.index(end):
            raise ValueError(f'{name}: reversed managed block')
    message = migrate(repo) if migrate_legacy and config_path.exists() else None
    config = load_config(repo) if config_path.exists() else new_config()
    if text_format is not None:
        config['text_format'] = 'xml' if text_format == 'dchxml' else text_format
    if fallback is not None:
        config['fallback_earlier'] = fallback
    previous = record['previous_hooks_path']
    prior = Path(previous)
    prior_dir = prior if prior.is_absolute() else repo.root / prior
    names = set(HOOKS)
    if prior_dir.is_dir():
        names.update(p.name for p in prior_dir.iterdir() if p.is_file() and not p.name.endswith('.sample'))
    source = Path(__file__).resolve().parents[2]
    atomic_write(runner, ('import sys\n' + f'sys.path.insert(0, {str(source)!r})\n'
                         'from apps.diptrace_git.__main__ import main\n'
                         'raise SystemExit(main())\n').encode())
    for name in sorted(names):
        old = (prior / name).as_posix()
        command = prefix + ' hook ' + name if name in HOOKS else ':'
        stop = 'if [ "$status" -ne 0 ]; then exit "$status"; fi\n' if name == 'pre-commit' else ''
        body = ('#!/bin/sh\n# diptrace-git managed hook\nstatus=0\n'
                + command + ' "$@" || status=$?\n' + stop
                + f'if [ -x {shlex.quote(old)} ]; then\n  {shlex.quote(old)} "$@"\n'
                + '  previous_status=$?\n  if [ "$previous_status" -ne 0 ]; then exit "$previous_status"; fi\nfi\nexit "$status"\n')
        path = hooks / name
        atomic_write(path, body.encode())
        path.chmod(path.stat().st_mode | 0o111)
    previous_settings = record.setdefault('previous_settings', {})
    for key in installed:
        if key not in previous_settings:
            previous_settings[key] = (record['previous_local_hooks_path'] if key == 'core.hooksPath'
                                      else None if key == 'alias.diptrace' else repo.config(key, local=True))
    record['installed'] = installed
    record['installed_alias'] = installed['alias.diptrace']
    record['resume_values'] = {key: [repo.config(key), value] for key, value in installed.items()}
    record['pending'] = True
    atomic_write(record_path, json_bytes(record))
    if (not config_path.exists() or text_format is not None or fallback is not None):
        atomic_write(config_path, json_bytes(config))
    marked_file(repo, '.gitattributes', ['*.git.asc filter=diptrace -text',
                                      '*.git.xml filter=diptrace -text', '*.git.json filter=diptrace -text'])
    refresh_ignore(repo)
    try:
        for key, value in installed.items():
            repo.run('config', '--local', key, value)
    except ValueError as error:
        raise OSError(f'{error}; installation is incomplete: rerun init or uninstall to restore prior settings') from error
    record['pending'] = False
    atomic_write(record_path, json_bytes(record))
    return message


def uninstall(repo):
    with internal_commands(), locked(repo):
        home = repo.common_dir / 'diptrace-git'
        record_path = home / 'installation.json'
        if not record_path.exists():
            raise ValueError('no local installation found')
        record = read_json(record_path)
        for key, value in record['installed'].items():
            allowed = record.get('resume_values', {}).get(key, [value]) if record.get('pending') else [value]
            if repo.config(key) not in allowed:
                raise ValueError(f'{key} changed since installation; refusing to overwrite it')
        for key, value in record['previous_settings'].items():
            if value is None:
                repo.run('config', '--local', '--unset-all', key, check=False)
            else:
                repo.run('config', '--local', key, value)
        marked_file(repo, '.gitignore', [])
        marked_file(repo, '.gitattributes', [])
        record_path.unlink()
