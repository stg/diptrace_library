"""Install reversible local hooks without modifying an existing hook program."""
from pathlib import Path
import shlex
import sys

from .config import CONFIG, load_config, new_config, validate_rule
from .files import atomic_write, json_bytes, read_json

START = '# BEGIN diptrace-git'
END = '# END diptrace-git'
HOOKS = ('pre-commit', 'post-checkout', 'post-merge', 'post-rewrite')


def ignore_rules(repo, rules):
    """Only replace our marked block; retain unrelated ignore entries verbatim."""
    path = repo.path('.gitignore')
    original = path.read_bytes() if path.exists() else b''
    lines = original.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip(b'\r\n') == START.encode()]
    ends = [i for i, line in enumerate(lines) if line.rstrip(b'\r\n') == END.encode()]
    if len(starts) != len(ends) or len(starts) > 1 or starts and starts[0] > ends[0]:
        raise ValueError('.gitignore has an incomplete diptrace-git block; repair its markers first')
    newline = b'\r\n' if b'\r\n' in original else b'\n'
    block = newline.join(line.encode('utf-8') for line in (START, *rules, END)) + newline if rules else b''
    if starts:
        updated = b''.join(lines[:starts[0]]) + block + b''.join(lines[ends[0] + 1:])
    elif block:
        updated = original + (newline if original and not original.endswith(b'\n') else b'') + block
    else:
        return
    atomic_write(path, updated)


def install(repo, *, text_format=None, fallback=None):
    config_path = repo.path(CONFIG)
    config = load_config(repo) if config_path.exists() else new_config()
    if text_format is not None:
        config['text_format'] = text_format
    if fallback is not None:
        config['fallback_earlier'] = fallback
    home = repo.common_dir / 'diptrace-git'
    record_path = home / 'installation.json'
    hooks = home / 'hooks'
    runner = home / 'runner.py'
    alias = '!' + ' '.join(shlex.quote(value) for value in
                          (Path(sys.executable).as_posix(), runner.resolve().as_posix()))
    if record_path.exists():
        record = read_json(record_path)
        if repo.config('core.hooksPath') != hooks.resolve().as_posix():
            raise ValueError('core.hooksPath changed since installation; resolve it before reinstalling')
        if repo.config('alias.diptrace') != record['installed_alias']:
            raise ValueError('alias.diptrace changed since installation; resolve it before reinstalling')
    else:
        effective = repo.config('core.hooksPath')
        if effective == hooks.resolve().as_posix():
            raise ValueError('installation record is missing; restore core.hooksPath before reinstalling')
        if repo.config('alias.diptrace') is not None:
            raise ValueError('alias.diptrace is already configured; choose another name for that alias before init')
        record = {'previous_local_hooks_path': repo.config('core.hooksPath', local=True),
                  'previous_hooks_path': repo.config('core.hooksPath', path=True)
                                         or (repo.common_dir / 'hooks').resolve().as_posix()}
    record['installed_alias'] = alias
    previous = record['previous_hooks_path']
    source = Path(__file__).resolve().parents[2]
    # Absolute installation paths belong only in local Git metadata, never in
    # the portable configuration or tracked per-design reconstruction JSON.
    atomic_write(runner, (
        'import sys\n'
        f'sys.path.insert(0, {str(source)!r})\n'
        'from apps.diptrace_git.__main__ import main\n'
        'raise SystemExit(main())\n').encode('utf-8'))
    for name in HOOKS:
        old_hook = (Path(previous) / name).as_posix()
        command = ' '.join(shlex.quote(value) for value in
                           (Path(sys.executable).as_posix(), runner.resolve().as_posix(), 'hook', name))
        stop = 'if [ "$status" -ne 0 ]; then exit "$status"; fi\n' if name == 'pre-commit' else ''
        contents = (
            '#!/bin/sh\n# diptrace-git managed hook\nstatus=0\n'
            f'{command} "$@" || status=$?\n' + stop +
            f'if [ -x {shlex.quote(old_hook)} ]; then\n'
            f'  {shlex.quote(old_hook)} "$@"\n'
            '  previous_status=$?\n'
            '  if [ "$previous_status" -ne 0 ]; then exit "$previous_status"; fi\n'
            'fi\nexit "$status"\n')
        path = hooks / name
        atomic_write(path, contents.encode('utf-8'))
        path.chmod(path.stat().st_mode | 0o111)
    atomic_write(record_path, json_bytes(record))
    atomic_write(config_path, json_bytes(config))
    ignore_rules(repo, config['rules'])
    repo.run('config', '--local', 'core.hooksPath', hooks.resolve().as_posix())
    repo.run('config', '--local', 'alias.diptrace', alias)


def change_rule(repo, pattern, *, remove=False):
    validate_rule(pattern)
    config = load_config(repo)
    if remove:
        if pattern not in config['rules']:
            raise ValueError(f'no such selection rule: {pattern}')
        config['rules'].remove(pattern)
    elif pattern not in config['rules']:
        config['rules'].append(pattern)
    ignore_rules(repo, config['rules'])
    atomic_write(repo.path(CONFIG), json_bytes(config))


def uninstall(repo):
    home = repo.common_dir / 'diptrace-git'
    record_path = home / 'installation.json'
    if not record_path.exists():
        raise ValueError('no local hook installation found')
    record = read_json(record_path)
    if repo.config('core.hooksPath') != (home / 'hooks').resolve().as_posix():
        raise ValueError('core.hooksPath changed since installation; refusing to overwrite its new setting')
    previous = record['previous_local_hooks_path']
    if previous is None:
        repo.run('config', '--local', '--unset', 'core.hooksPath')
    else:
        repo.run('config', '--local', 'core.hooksPath', previous)
    alias = repo.config('alias.diptrace', local=True)
    if alias == record['installed_alias']:
        repo.run('config', '--local', '--unset', 'alias.diptrace')
    ignore_rules(repo, [])
    record_path.unlink()
    # Keep the disposable cache and inert hook files. Another worktree may
    # still be finishing a hook; removing the configured path already disables
    # our integration without deleting any designs or companions.
