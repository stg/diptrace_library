"""Track generated DipTrace artifacts with ordinary Git commands."""
import argparse
from contextlib import redirect_stdout
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

from lib import ConversionReport
from apps.common.cli import Console, PROCESSING_ERRORS, add_report_argument
from .config import CONFIG, FAMILIES, ConfigurationError, load_config
from .files import read_json
from .git import Repository
from .locking import ACTIVE, internal_commands
from .setup import change_selection, install, uninstall
from .sync import error_message, synchronize


def diagnostics(result, console, *, include_errors=True):
    for message in result.warnings:
        console.diagnostic('warning', message)
    console.report(ConversionReport(result.notices), include_errors=include_errors)


def show(result, console):
    diagnostics(result, console)
    for message in (*result.actions, *result.pending):
        console.info(message)
    if not result.actions and not result.pending:
        console.info('No conversion needed.')


def monitor_reply():
    sys.stdout.buffer.write((str(time.time_ns()) + '\0/\0').encode())
    sys.stdout.buffer.flush()


def main(argv=None):
    parser = argparse.ArgumentParser(prog='diptrace_git', description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'), help='target Git working directory')
    add_report_argument(parser)
    commands = parser.add_subparsers(dest='command', required=True,
        metavar='{init,enable,disable,selection,sync,export,rebuild,check,uninstall,commit}')
    init = commands.add_parser('init', help='install local integration and bootstrap existing companions')
    init.add_argument('--text-format', choices=('xml', 'asc'))
    init.add_argument('--fallback-earlier', action='store_const', const=True, default=None)
    init.add_argument('--migrate', action='store_true', help='migrate legacy artifacts and existing selection')
    for name in ('enable', 'disable'):
        cmd = commands.add_parser(name, help=name + ' designs matched by Git pathspecs')
        cmd.add_argument('pathspecs', nargs='+', help='quoted Git pathspecs relative to the repository root')
        if name == 'enable':
            cmd.add_argument('--untrack', action='store_true', help='migrate already tracked native files, keeping local files')
    commands.add_parser('selection', help='show ordered enable/disable pathspecs')
    for name in ('sync', 'export', 'rebuild', 'check'):
        cmd = commands.add_parser(name, help={'sync': 'synchronize selected designs',
            'export': 'regenerate artifacts from native designs', 'rebuild': 'rebuild native designs',
            'check': 'preview synchronization'}[name])
        cmd.add_argument('--verify', action='store_true')
        cmd.add_argument('files', nargs='*', help='selected native or artifact paths relative to the repository')
        if name != 'check':
            cmd.add_argument('--stage', action='store_true')
            cmd.add_argument('--untrack', action='store_true', help='remove selected native files from the index, keeping local files')
        if name in ('export', 'rebuild'):
            cmd.add_argument('--force', action='store_true')
    commands.add_parser('uninstall', help='restore prior Git settings; keep designs and artifacts')
    commands.add_parser('commit', help='compatibility wrapper: sync/stage, then git commit')
    hook = commands.add_parser('hook')
    hook.add_argument('name', choices=('pre-commit', 'post-checkout', 'post-merge', 'post-rewrite', 'post-index-change'))
    hook.add_argument('arguments', nargs=argparse.REMAINDER)
    monitor = commands.add_parser('monitor')
    monitor.add_argument('arguments', nargs=argparse.REMAINDER)
    filter_cmd = commands.add_parser('filter')
    filter_cmd.add_argument('mode', choices=('clean', 'smudge'))
    filter_cmd.add_argument('path')
    for cmd in commands.choices.values():
        add_report_argument(cmd, default=argparse.SUPPRESS)
    args, remaining = parser.parse_known_args(argv)
    if args.command != 'commit' and remaining:
        parser.error('unrecognized arguments: ' + ' '.join(remaining))
    if getattr(args, 'force', False) and not args.files:
        parser.error('--force requires explicit design paths')
    incoming = sys.stdin.buffer.read() if args.command == 'filter' else None
    if os.environ.get(ACTIVE) and args.command in ('hook', 'monitor', 'filter'):
        if incoming is not None:
            sys.stdout.buffer.write(incoming)
        elif args.command == 'monitor':
            monitor_reply()
        return 0
    console = Console(args.report_level)
    config_action = False
    try:
        with internal_commands():
            repo = Repository(args.repo)
            if args.command == 'init':
                config_action = True
                message = install(repo, text_format=args.text_format, fallback=args.fallback_earlier,
                                  migrate_legacy=args.migrate)
                config_action = False
                if message:
                    console.info(message)
                show(synchronize(repo), console)
                console.info('Installed local integration. Commit settings, .gitignore, .gitattributes and generated artifacts.')
            elif args.command in ('enable', 'disable'):
                config_action = True
                change_selection(repo, args.pathspecs, enabled=args.command == 'enable')
                config_action = False
                if args.command == 'enable':
                    show(synchronize(repo, untrack=args.untrack), console)
                console.info(args.command + ': ' + ' '.join(args.pathspecs))
            elif args.command == 'selection':
                for rule in load_config(repo)['rules']:
                    print(('enable ' if rule['enabled'] else 'disable ') + shlex.join(rule['pathspecs']))
            elif args.command == 'uninstall':
                config_action = True
                uninstall(repo)
                config_action = False
                console.info('Restored previous Git settings. Designs, artifacts and portable settings were kept.')
            elif args.command == 'filter':
                if args.mode == 'clean' and repo.path(CONFIG).is_file():
                    binary, separator, extension = args.path.rpartition('.git.')
                    if (separator and Path(binary).suffix.lower().lstrip('.') in FAMILIES
                            and repo.selected({binary}, load_config(repo)['rules'])):
                        path = repo.state_dir / 'hook-error.json'
                        if path.exists():
                            raise ValueError(read_json(path)['message'])
                sys.stdout.buffer.write(incoming)
            elif args.command in ('hook', 'monitor'):
                if repo.path(CONFIG).is_file():
                    name = getattr(args, 'name', None)
                    installed = (name in ('post-checkout', 'post-merge', 'post-rewrite') or
                                 name == 'post-index-change' and args.arguments[:1] == ['1'])
                    result = synchronize(repo, installed=installed, require_installation=True)
                    if name == 'pre-commit' and any(a.startswith('export ') for a in result.actions):
                        raise ValueError('native edit arrived after Git prepared the index; stage its artifacts and retry')
                    with redirect_stdout(sys.stderr):
                        diagnostics(result, console)
                if args.command == 'monitor':
                    monitor_reply()
            elif args.command == 'commit':
                show(synchronize(repo, stage=True), console)
                if remaining[:1] == ['--']:
                    remaining = remaining[1:]
                env = dict(os.environ)
                env.pop(ACTIVE, None)
                return subprocess.call(['git', '-C', str(repo.root), 'commit', *remaining], env=env)
            else:
                show(synchronize(repo, direction={'export': 'binary', 'rebuild': 'text'}.get(args.command, 'auto'),
                    force=getattr(args, 'force', False), stage=getattr(args, 'stage', False),
                    untrack=getattr(args, 'untrack', False), verify=args.verify,
                    dry_run=args.command == 'check', files=args.files), console)
        return 0
    except (*PROCESSING_ERRORS, subprocess.SubprocessError) as error:
        partial = getattr(error, 'diptrace_result', None)
        if partial is not None:
            with redirect_stdout(sys.stderr):
                diagnostics(partial, console, include_errors=False)
            if args.command not in ('monitor', 'filter', 'hook'):
                for action in partial.actions:
                    console.info(action)
        console.failure('diptrace-git failed', error_message(error))
        if args.command == 'monitor':
            monitor_reply()  # Required clean filtering/pre-commit handles the recorded failure.
            return 0
        if args.command == 'hook' and args.name != 'pre-commit':
            console.diagnostic('error', 'Git has already updated its files. Resolve the issue and run sync; '
                               'the Git operation is not rolled back.')
        return 2 if isinstance(error, ConfigurationError) or config_action and isinstance(error, ValueError) else 1


if __name__ == '__main__':
    raise SystemExit(main())
