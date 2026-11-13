"""Small Git commands; Git itself owns matching, staging and repository state."""
import os
from pathlib import Path
import subprocess

from .files import atomic_write, digest, json_bytes
from .locking import ACTIVE


class Repository:
    def __init__(self, path='.'):
        self.root = Path(path).resolve()
        self.root = Path(self.run('rev-parse', '--show-toplevel').decode().strip()).resolve()
        self.state_dir = self.git_path('diptrace-git')
        common = Path(self.run('rev-parse', '--git-common-dir').decode().strip())
        self.common_dir = common if common.is_absolute() else self.root / common

    def run(self, *args, data=None, check=True):
        prefix = ['git', '-C', str(self.root)]
        env = None
        if os.environ.get(ACTIVE):
            # An outer `git --literal-pathspecs ...` must not change the
            # meaning of our own discovery patterns or committed selection.
            modes = {'GIT_LITERAL_PATHSPECS', 'GIT_GLOB_PATHSPECS',
                     'GIT_NOGLOB_PATHSPECS', 'GIT_ICASE_PATHSPECS'}
            env = {key: value for key, value in os.environ.items() if key not in modes}
        if os.environ.get(ACTIVE) and args[:1] != ('config',):
            prefix += ['-c', 'core.fsmonitor=', '-c', 'core.hooksPath=' + str(self.root / '.git/diptrace-git/no-hooks')]
        result = subprocess.run([*prefix, *args], input=data, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check and result.returncode:
            raise ValueError(result.stderr.decode('utf-8', errors='replace').strip()
                             or f'git {args[0]} failed')
        return result.stdout

    def git_path(self, name):
        path = Path(self.run('rev-parse', '--git-path', name).decode().strip())
        return path if path.is_absolute() else self.root / path

    def path(self, relative):
        """Tracked metadata never grants permission to write outside the worktree."""
        path = self.root / relative
        if Path(relative).is_absolute() or '\\' in relative:
            raise ValueError(f'expected a repository-relative path: {relative!r}')
        try:
            path.resolve().relative_to(self.root)
        except ValueError:
            raise ValueError(f'path escapes repository: {relative!r}') from None
        if '.git' in (part.lower() for part in Path(relative).parts) or path.is_symlink():
            raise ValueError(f'unsupported metadata or symbolic-link path: {relative!r}')
        return path

    def names(self, *args):
        return {os.fsdecode(name) for name in self.run(args[0], '-z', *args[1:]).split(b'\0') if name}

    def config(self, key, *, local=False, path=False):
        args = ['config', *(['--local'] if local else []), *(['--path'] if path else []), '--get', key]
        result = self.run(*args, check=False).decode().rstrip('\n')
        return result or None

    def legacy_selected(self, names, rules):
        """Evaluate real gitignore syntax against virtual binary paths too.

        A clone may have only companions, with no DCH on disk. An isolated empty
        worktree lets check-ignore match these names without consulting unrelated
        ignore rules or manufacturing binary files. No design data goes here.
        """
        if not names or not rules:
            return set()
        matcher = self.state_dir / 'matcher'
        git_dir, worktree = matcher / 'git', matcher / 'worktree'
        worktree.mkdir(parents=True, exist_ok=True)
        env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        if not (git_dir / 'HEAD').exists():
            subprocess.run(['git', '-c', 'core.longpaths=true', 'init', '--bare', '-q', str(git_dir)], env=env, check=True)
        rule_file = matcher / 'rules'
        atomic_write(rule_file, ('\n'.join(rules) + '\n').encode('utf-8'))
        command = ['git', '-c', 'core.longpaths=true', '--git-dir=' + str(git_dir), '--work-tree=' + str(worktree),
                   '-c', 'core.excludesFile=' + str(rule_file),
                   '-c', 'core.ignorecase=' + (self.config('core.ignorecase') or 'false'),
                   'check-ignore', '--no-index', '-z', '--stdin']
        result = subprocess.run(command, cwd=worktree, env=env,
                                input=b'\0'.join(os.fsencode(n) for n in sorted(names)) + b'\0',
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode not in (0, 1):
            raise ValueError(result.stderr.decode(errors='replace'))
        return {os.fsdecode(name) for name in result.stdout.split(b'\0') if name}

    def selected(self, names, rules):
        """Let Git evaluate pathspecs against an index of virtual native names.

        No design bytes are copied. This also matches binaries absent in a clone.
        Rules are ordered enable/disable operations; each operation accepts Git's
        normal include/exclude pathspec syntax as a group.
        """
        if not names or not rules:
            return set()
        matcher = self.state_dir / 'pathspecs'
        git_dir, worktree = matcher / 'git', matcher / 'worktree'
        worktree.mkdir(parents=True, exist_ok=True)
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        index = matcher / 'index'
        env['GIT_INDEX_FILE'] = str(index.resolve())
        prefix = ['git', '--git-dir=' + str(git_dir.resolve()), '--work-tree=' + str(worktree.resolve()),
                  '-c', 'core.longpaths=true', '-c', 'core.fsmonitor=',
                  '-c', 'core.hooksPath=' + str((matcher / 'no-hooks').resolve())]
        def run(*args, data=None):
            result = subprocess.run([*prefix, *args], env=env, input=data,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode:
                raise ValueError(result.stderr.decode('utf-8', 'replace').strip())
            return result.stdout
        if not (git_dir / 'HEAD').exists():
            subprocess.run(['git', '-c', 'core.longpaths=true', 'init', '--bare', '-q', str(git_dir)], env=env, check=True)
        def index_digest():
            try:
                return digest(index.read_bytes())
            except FileNotFoundError:
                return None
        # The inventory and index form one disposable cache. A saved name list
        # alone cannot prove that Git's matching index still exists or agrees.
        inventory = {'names': sorted(names), 'index_sha256': index_digest()}
        saved = matcher / 'names.json'
        if (inventory['index_sha256'] is None or not saved.exists()
                or saved.read_bytes() != json_bytes(inventory)):
            oid = run('hash-object', '-w', '--stdin', data=b'').strip()
            index.unlink(missing_ok=True)
            run('read-tree', '--empty')
            data = b''.join(b'100644 ' + oid + b'\t' + os.fsencode(name) + b'\0' for name in sorted(names))
            run('update-index', '-z', '--index-info', data=data)
            inventory['index_sha256'] = index_digest()
            if inventory['index_sha256'] is None:
                raise ValueError('Git did not create its temporary selection index')
            atomic_write(saved, json_bytes(inventory))
        chosen = set()
        for rule in rules:
            found = {os.fsdecode(n) for n in run('ls-files', '-z', '--', *rule['pathspecs']).split(b'\0') if n}
            if rule['enabled']:
                chosen.update(found)
            else:
                chosen.difference_update(found)
        if index_digest() != inventory['index_sha256']:
            raise ValueError('Git selection cache changed during matching; retry the operation')
        return chosen

    def stage(self, names):
        if names:
            self.run('add', '--', *(':(literal)' + name for name in sorted(names)))
