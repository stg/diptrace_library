"""Keep DipTrace binary working files and tracked text companions synchronized."""
import argparse
from pathlib import Path
import subprocess

from lib import ConversionReport
from apps.common.cli import Console, PROCESSING_ERRORS, add_report_argument
from .config import CONFIG, load_config
from .git import Repository
from .setup import change_rule, install, uninstall
from .sync import synchronize


def show(result, console):
    for message in result.warnings:
        console.diagnostic('warning', message)
    console.report(ConversionReport(result.notices))
    for action in result.actions:
        console.info(action)
    for pending in result.pending:
        console.info(pending)
    if not result.actions and not result.pending:
        console.info('No conversion needed.')


def main(argv=None):
    parser = argparse.ArgumentParser(prog='diptrace_git', description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'), help='target Git working directory')
    add_report_argument(parser)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='install local hooks, preserving existing hooks')
    init.add_argument('--text-format', choices=('dchxml', 'asc'))
    init.add_argument('--fallback-earlier', action='store_const', const=True, default=None,
                      help='allow an earlier supported binary version, with a warning')
    rules = commands.add_parser('rules', help='list, add or remove Git-style selection rules')
    rules.add_argument('action', choices=('list', 'add', 'remove'))
    rules.add_argument('pattern', nargs='?')
    for name in ('sync', 'export', 'rebuild', 'check'):
        command = commands.add_parser(name, help={
            'sync': 'convert whichever side changed', 'export': 'update text from binaries',
            'rebuild': 'update binaries from text', 'check': 'preview synchronization without writing designs',
        }[name])
        command.add_argument('--verify', action='store_true', help='check content even when file metadata matches')
        command.add_argument('files', nargs='*', help='optional selected binary or companion paths, relative to the repository')
        if name != 'check':
            command.add_argument('--stage', action='store_true', help='stage generated text and JSON companions')
            command.add_argument('--untrack', action='store_true', help='remove selected DCH files from the index, keeping working files')
        if name in ('export', 'rebuild'):
            command.add_argument('--force', action='store_true', help='explicitly choose this direction even for conflicting changes')
    commands.add_parser('uninstall', help='restore hooks and remove our ignore entries; keep design files')
    commands.add_parser('commit', help='synchronize and stage generated companions, then pass all arguments to git commit')
    hook = commands.add_parser('hook', help='run an installed Git hook (used internally)')
    hook.add_argument('name', choices=('pre-commit', 'post-checkout', 'post-merge', 'post-rewrite'))
    hook.add_argument('arguments', nargs=argparse.REMAINDER)
    for command in commands.choices.values():
        # Accept the shared option on either side of the subcommand.
        add_report_argument(command, default=argparse.SUPPRESS)
    args, remaining = parser.parse_known_args(argv)
    if args.command != 'commit' and remaining:
        parser.error('unrecognized arguments: ' + ' '.join(remaining))
    if args.command == 'rules' and args.action != 'list' and args.pattern is None:
        parser.error('rules add/remove requires a quoted pattern')
    if getattr(args, 'force', False) and not args.files:
        parser.error('--force requires explicit design paths; unchanged originals are not rebuilt in bulk')
    console = Console(args.report_level)
    try:
        repo = Repository(args.repo)
        if args.command == 'init':
            install(repo, text_format=args.text_format, fallback=args.fallback_earlier)
            console.info('Installed diptrace-git hooks. Commit .diptrace-git.json and .gitignore with your companions.')
            show(synchronize(repo, direction='text'), console)
        elif args.command == 'rules':
            if args.action == 'list':
                print('\n'.join(load_config(repo)['rules']) or 'No selected designs.')
            else:
                change_rule(repo, args.pattern, remove=args.action == 'remove')
                console.info(f'{args.action}: {args.pattern}')
        elif args.command == 'uninstall':
            uninstall(repo)
            console.info('Restored previous hooks and removed managed ignore entries. Design files and settings were kept.')
        elif args.command == 'commit':
            show(synchronize(repo, stage=True), console)
            if remaining[:1] == ['--']:
                remaining = remaining[1:]
            return subprocess.call(['git', '-C', str(repo.root), 'commit', *remaining])
        elif args.command == 'hook':
            if not repo.path(CONFIG).is_file():
                return 0  # Checked out a revision before this tool was configured.
            result = synchronize(repo, direction='auto' if args.name == 'pre-commit' else 'text',
                                 stage=args.name == 'pre-commit')
            show(result, console)
        else:
            result = synchronize(repo,
                direction={'export': 'binary', 'rebuild': 'text'}.get(args.command, 'auto'),
                force=getattr(args, 'force', False), stage=getattr(args, 'stage', False),
                untrack=getattr(args, 'untrack', False), verify=args.verify,
                dry_run=args.command == 'check', files=args.files)
            show(result, console)
        return 0
    except (*PROCESSING_ERRORS, subprocess.SubprocessError) as error:
        console.failure('diptrace-git failed', error)
        if args.command == 'hook' and args.name != 'pre-commit':
            console.diagnostic('error', 'Git has already updated the working tree. Resolve the issue and run sync; '
                               'the Git operation is not rolled back.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
