"""Exercise conversion safety through real Git commands as well as the CLI."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from lib import ConversionReport, new_schematic, new_symbol, read, serialize
from apps.diptrace_git.__main__ import main
from apps.diptrace_git.config import CONFIG
from apps.diptrace_git.files import Stamp
from apps.diptrace_git.git import Repository
from apps.diptrace_git.setup import change_rule, install, uninstall
from apps.diptrace_git.sync import synchronize


def design(value='10k', version=52):
    document = new_schematic()
    part = document.one('/Schematic/Components').append(new_symbol('Resistor', 'R1'))
    part['Value'] = value
    return serialize(document, format='dch', version=version, report=ConversionReport())


class GitTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name).resolve()
        self.root = self.folder / 'working tree'
        self.root.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.repo = Repository(self.root)
        self.repo.run('config', 'user.name', 'Fixture')
        self.repo.run('config', 'user.email', 'fixture@example.invalid')
        self.repo.run('config', 'core.autocrlf', 'false')
        self.repo.run('config', 'commit.gpgsign', 'false')
        install(self.repo)
        change_rule(self.repo, '*.dch')
        self.binary = self.root / 'design.dch'
        self.text = self.root / 'design.dchxml'
        self.metadata = self.root / 'design.dch.git.json'
        self.binary.write_bytes(design())

    def export(self, **options):
        return synchronize(self.repo, **options)

    def edit_text(self, value):
        document = read(self.text, report=ConversionReport())
        document.one('/Schematic/Components/Part')['Value'] = value
        self.text.write_bytes(serialize(document, format='dchxml', version=52, report=ConversionReport()))

    def value(self, path=None):
        return read(path or self.binary, report=ConversionReport()).one('/Schematic/Components/Part')['Value']

    def commit(self, message='fixture'):
        self.repo.run('add', '--all')
        self.repo.run('commit', '-qm', message)

    def test_initial_export_preserves_original_and_remembers_version(self):
        before = self.binary.read_bytes(), Stamp.read(self.binary)
        result = self.export(stage=True)
        self.assertEqual((self.binary.read_bytes(), Stamp.read(self.binary)), before)
        self.assertEqual(json.loads(self.metadata.read_text())['binary']['version'], 52)
        self.assertEqual(result.staged, {'design.dchxml', 'design.dch.git.json'})
        self.assertNotIn('design.dch', self.repo.names('ls-files', '--cached'))
        self.assertEqual(self.repo.run('check-ignore', 'design.dch').strip(), b'design.dch')
        self.assertTrue((self.repo.state_dir / 'state.json').exists())

    def test_other_tool_json_companions_are_left_alone(self):
        other = self.root / 'design.dch.json'
        original = b'other tool metadata, not ours'
        other.write_bytes(original)
        self.export()
        self.assertEqual(other.read_bytes(), original)
        self.assertTrue(self.metadata.exists())
        self.assertEqual(self.metadata.name, 'design.dch.git.json')

    def test_unchanged_pair_reads_neither_design_body(self):
        self.export()
        original = Path.read_bytes
        def guarded(path):
            if path in (self.binary, self.text):
                raise AssertionError('unchanged design body was read')
            return original(path)
        with patch.object(Path, 'read_bytes', guarded), patch('apps.diptrace_git.sync.parse') as parse:
            self.assertEqual(self.export().actions, [])
        parse.assert_not_called()

    def test_timestamp_and_line_ending_changes_do_not_rebuild_binary(self):
        self.export()
        before = self.binary.read_bytes(), Stamp.read(self.binary)
        stamp = self.text.stat()
        os.utime(self.text, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000))
        self.assertEqual(self.export().actions, [])
        self.text.write_bytes(self.text.read_bytes().replace(b'\n', b'\r\n'))
        self.assertEqual(self.export().actions, [])
        self.assertEqual((self.binary.read_bytes(), Stamp.read(self.binary)), before)

    def test_missing_cache_is_verified_without_rewriting_original(self):
        self.export()
        before = self.binary.read_bytes(), Stamp.read(self.binary)
        (self.repo.state_dir / 'state.json').unlink()
        self.assertTrue(self.export().actions[0].startswith('verify'))
        self.assertEqual((self.binary.read_bytes(), Stamp.read(self.binary)), before)

    def test_missing_or_corrupt_cache_never_overwrites_disagreeing_pair(self):
        self.export()
        self.edit_text('22k')
        before = self.binary.read_bytes(), self.text.read_bytes()
        (self.repo.state_dir / 'state.json').write_text('{bad JSON')
        with self.assertRaisesRegex(ValueError, 'no synchronization baseline'):
            self.export()
        self.assertEqual((self.binary.read_bytes(), self.text.read_bytes()), before)

    def test_binary_change_exports_without_rebuilding_binary(self):
        self.export()
        self.binary.write_bytes(design('33k', version=51))
        before = self.binary.read_bytes(), Stamp.read(self.binary)
        result = self.export()
        self.assertEqual(self.value(self.text), '33k')
        self.assertEqual(json.loads(self.metadata.read_text())['binary']['version'], 51)
        self.assertEqual((self.binary.read_bytes(), Stamp.read(self.binary)), before)
        self.assertEqual(len(result.actions), 1)

    def test_text_change_rebuilds_recorded_version_once(self):
        self.export()
        self.edit_text('47k')
        self.assertTrue(self.export().actions[0].startswith('rebuild'))
        self.assertEqual(self.value(), '47k')
        self.assertEqual(read(self.binary).metadata['source_version'], 52)
        stamp = Stamp.read(self.binary)
        self.assertEqual(self.export().actions, [])
        self.assertEqual(Stamp.read(self.binary), stamp)

    def test_conflict_requires_explicit_direction(self):
        self.export()
        self.binary.write_bytes(design('33k'))
        self.edit_text('47k')
        before = self.binary.read_bytes(), self.text.read_bytes()
        with self.assertRaisesRegex(ValueError, 'both binary and text changed'):
            self.export()
        self.assertEqual((self.binary.read_bytes(), self.text.read_bytes()), before)
        self.export(direction='text', force=True)
        self.assertEqual(self.value(), '47k')

    def test_missing_binary_can_be_reconstructed(self):
        self.export()
        self.binary.unlink()
        self.assertTrue(self.export(direction='text').actions[0].startswith('rebuild'))
        self.assertEqual(self.value(), '10k')

    def test_unsupported_version_errors_and_explicit_fallback_warns(self):
        self.export()
        metadata = json.loads(self.metadata.read_text())
        metadata['binary']['version'] = 999
        self.metadata.write_text(json.dumps(metadata))
        before = self.binary.read_bytes()
        with self.assertRaisesRegex(ValueError, 'cannot write version'):
            self.export(direction='text', force=True)
        self.assertEqual(self.binary.read_bytes(), before)
        config = json.loads((self.root / CONFIG).read_text())
        config['fallback_earlier'] = True
        (self.root / CONFIG).write_text(json.dumps(config))
        result = self.export(direction='text', force=True)
        self.assertIn('earlier schema 52', result.warnings[0])
        self.assertEqual(read(self.binary).metadata['source_version'], 52)

    def test_report_level_is_accepted_before_and_after_subcommand(self):
        for arguments in (['--report-level', 'error', 'check'],
                          ['check', '--report-level', 'info']):
            output, errors = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                status = main(['--repo', str(self.root), *arguments])
            self.assertEqual(status, 0, errors.getvalue())
            self.assertIn('Info: export', output.getvalue())
            self.assertFalse(self.text.exists())  # check remains read-only.

    def test_asc_is_an_alternative_not_a_second_companion(self):
        install(self.repo, text_format='asc')
        self.export()
        self.assertTrue((self.root / 'design.asc').exists())
        self.assertFalse(self.text.exists())
        self.binary.unlink()
        self.export()
        self.assertEqual(self.value(), '10k')

    def test_rules_use_git_exclusions_and_preserve_unrelated_ignores(self):
        ignore = self.root / '.gitignore'
        ignore.write_bytes(b'# existing\noutput/\n' + ignore.read_bytes())
        archive = self.root / 'archive'
        archive.mkdir()
        (archive / 'old.dch').write_bytes(b'not a design')
        (archive / 'old.dch.git.json').write_text('{unrelated JSON')
        change_rule(self.repo, '!archive/**')
        self.export()
        self.assertTrue(ignore.read_bytes().startswith(b'# existing\noutput/\n'))
        self.assertFalse((archive / 'old.dchxml').exists())
        change_rule(self.repo, '*.dch', remove=True)
        self.assertEqual(self.export().actions, [])

    def test_existing_tracked_binary_needs_explicit_migration(self):
        self.repo.run('add', '-f', '--', 'design.dch')
        before = self.binary.read_bytes()
        with self.assertRaisesRegex(ValueError, 'sync --untrack'):
            self.export()
        self.export(untrack=True, stage=True)
        self.assertEqual(self.binary.read_bytes(), before)
        self.assertNotIn('design.dch', self.repo.names('ls-files', '--cached'))

    def test_actual_commit_hook_exports_and_stages_changed_binary(self):
        self.commit()
        self.assertIn('design.dchxml', self.repo.names('ls-files', '--cached'))
        self.assertNotIn('design.dch', self.repo.names('ls-files', '--cached'))
        self.binary.write_bytes(design('100k'))
        (self.root / 'notes.txt').write_text('another staged change')
        self.repo.run('add', 'notes.txt')
        self.repo.run('commit', '-qm', 'binary edit')
        self.assertEqual(self.value(self.text), '100k')
        self.assertEqual(self.repo.run('status', '--porcelain'), b'')

    def test_actual_checkout_hook_rebuilds_only_changed_text(self):
        self.commit('first')
        first = self.repo.run('rev-parse', 'HEAD').decode().strip()
        self.binary.write_bytes(design('220k'))
        self.repo.run('diptrace', 'commit', '-qm', 'second')
        self.repo.run('checkout', '--detach', first)
        self.assertEqual(self.value(), '10k')
        before = self.binary.read_bytes(), Stamp.read(self.binary)
        self.repo.run('checkout', '--detach', first)
        self.assertEqual((self.binary.read_bytes(), Stamp.read(self.binary)), before)

    def test_commit_command_includes_binary_only_changes(self):
        self.commit()
        self.binary.write_bytes(design('330k'))
        self.repo.run('diptrace', 'commit', '-qm', 'binary-only change')
        self.assertEqual(self.value(self.text), '330k')
        self.assertEqual(self.repo.run('status', '--porcelain'), b'')

    def test_fresh_clone_init_reconstructs_missing_binary(self):
        self.commit()
        clone = self.folder / 'clone'
        subprocess.run(['git', 'clone', '-q', str(self.root), str(clone)], check=True)
        self.assertFalse((clone / 'design.dch').exists())
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--repo', str(clone), 'init']), 0)
        self.assertEqual(self.value(clone / 'design.dch'), '10k')

    def test_linked_worktree_uses_separate_cache(self):
        self.commit()
        linked = self.folder / 'linked'
        self.repo.run('worktree', 'add', '-b', 'linked', str(linked))
        other = Repository(linked)
        self.assertNotEqual(other.state_dir.resolve(), self.repo.state_dir.resolve())
        self.assertTrue((other.state_dir / 'state.json').exists())
        self.assertEqual(self.value(linked / 'design.dch'), '10k')

    def test_custom_hook_is_chained_and_restored(self):
        uninstall(self.repo)
        existing = self.root / '.existing-hooks'
        existing.mkdir()
        hook = existing / 'pre-commit'
        contents = b'#!/bin/sh\nprintf called > hook-called\n'
        hook.write_bytes(contents)
        hook.chmod(hook.stat().st_mode | 0o111)
        self.repo.run('config', 'core.hooksPath', '.existing-hooks')
        install(self.repo)
        self.commit()
        self.assertTrue((self.root / 'hook-called').exists())
        self.assertEqual(hook.read_bytes(), contents)
        uninstall(self.repo)
        self.assertEqual(self.repo.config('core.hooksPath'), '.existing-hooks')
        self.assertEqual(hook.read_bytes(), contents)

    def test_preview_and_invalid_cli_do_not_replace_designs(self):
        before = self.binary.read_bytes(), Stamp.read(self.binary)
        self.assertTrue(self.export(dry_run=True).actions)
        self.assertFalse(self.text.exists())
        self.assertFalse(self.metadata.exists())
        self.assertEqual((self.binary.read_bytes(), Stamp.read(self.binary)), before)
        errors = io.StringIO()
        with redirect_stderr(errors), redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--repo', str(self.root), 'rules', 'add', '**']), 1)
        self.assertNotIn('Traceback', errors.getvalue())

    def test_metadata_cannot_redirect_writes_outside_repository(self):
        self.export()
        metadata = json.loads(self.metadata.read_text())
        metadata['text']['path'] = '../outside.dchxml'
        self.metadata.write_text(json.dumps(metadata))
        with self.assertRaisesRegex(ValueError, 'invalid reconstruction metadata'):
            self.export()
        self.assertFalse((self.folder / 'outside.dchxml').exists())

    def test_exported_but_unstaged_companions_can_be_staged_later(self):
        self.export()
        self.assertNotIn('design.dchxml', self.repo.names('ls-files', '--cached'))
        self.export(stage=True)
        self.assertIn('design.dchxml', self.repo.names('ls-files', '--cached'))

    def test_staged_text_snapshot_is_not_replaced_by_a_new_export(self):
        self.commit()
        self.binary.write_bytes(design('22k'))
        self.export()
        self.repo.run('add', '--', 'design.dchxml')
        staged = self.repo.run('show', ':design.dchxml')
        self.binary.write_bytes(design('33k'))
        with self.assertRaisesRegex(ValueError, 'replace a staged companion'):
            self.export(stage=True)
        self.assertEqual(self.repo.run('show', ':design.dchxml'), staged)
        self.assertEqual(self.text.read_bytes(), staged)

    def test_later_failure_keeps_completed_pairs_in_the_cache(self):
        (self.root / 'zz-broken.dch').write_bytes(b'broken')
        with self.assertRaises(ValueError):
            self.export()
        state = json.loads((self.repo.state_dir / 'state.json').read_text())
        self.assertIn('design.dch', state['files'])
        (self.root / 'zz-broken.dch').unlink()
        with patch('apps.diptrace_git.sync.parse', side_effect=AssertionError('unnecessary parse')):
            self.assertEqual(self.export().actions, [])

    def test_force_targets_only_named_designs(self):
        other = self.root / 'other.dch'
        other.write_bytes(design('1k'))
        self.export()
        before = other.read_bytes(), Stamp.read(other)
        self.edit_text('2k')
        self.export(direction='text', force=True, files=['design.dch'])
        self.assertEqual(self.value(), '2k')
        self.assertEqual((other.read_bytes(), Stamp.read(other)), before)
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
            main(['--repo', str(self.root), 'rebuild', '--force'])
        self.assertEqual(stopped.exception.code, 2)

    def test_post_checkout_conflict_preserves_locally_edited_binary(self):
        self.commit('first')
        first = self.repo.run('rev-parse', 'HEAD').decode().strip()
        self.binary.write_bytes(design('22k'))
        self.repo.run('diptrace', 'commit', '-qm', 'second')
        self.binary.write_bytes(design('local unsaved commit'))
        before = self.binary.read_bytes()
        with self.assertRaisesRegex(ValueError, 'both binary and text changed'):
            self.repo.run('checkout', '--detach', first)
        self.assertEqual(self.binary.read_bytes(), before)
        self.assertEqual(self.repo.run('rev-parse', 'HEAD').decode().strip(), first)

    def test_actual_fast_forward_pull_refreshes_binary(self):
        self.commit('first')
        clone = self.folder / 'pull-clone'
        subprocess.run(['git', 'clone', '-q', str(self.root), str(clone)], check=True)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--repo', str(clone), 'init']), 0)
        self.binary.write_bytes(design('470k'))
        self.repo.run('diptrace', 'commit', '-qm', 'remote binary edit')
        other = Repository(clone)
        other.run('pull', '--ff-only')
        self.assertEqual(self.value(clone / 'design.dch'), '470k')

    def test_uppercase_extension_and_unicode_filename(self):
        self.binary.unlink()
        source = self.root / 'Power \u00b5.DCH'
        source.write_bytes(design())
        change_rule(self.repo, '*.DCH')
        self.export()
        self.assertTrue((self.root / 'Power \u00b5.dchxml').exists())
        self.assertEqual(self.export().actions, [])

    def test_actual_rebase_pull_refreshes_binary(self):
        self.commit('first')
        clone = self.folder / 'rebase-clone'
        subprocess.run(['git', 'clone', '-q', str(self.root), str(clone)], check=True)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--repo', str(clone), 'init']), 0)
        other = Repository(clone)
        other.run('config', 'user.name', 'Fixture')
        other.run('config', 'user.email', 'fixture@example.invalid')
        other.run('config', 'commit.gpgsign', 'false')
        (clone / 'notes.txt').write_text('independent local change')
        other.run('add', 'notes.txt')
        other.run('commit', '-qm', 'local note')
        self.binary.write_bytes(design('680k'))
        self.repo.run('diptrace', 'commit', '-qm', 'remote binary edit')
        other.run('pull', '--rebase')
        self.assertEqual(self.value(clone / 'design.dch'), '680k')
        self.assertTrue((clone / 'notes.txt').exists())

    def test_invalid_merged_text_does_not_replace_binary_or_print_traceback(self):
        self.export()
        before = self.binary.read_bytes(), Stamp.read(self.binary)
        self.text.write_text('<<<<<<< ours\nnot XML\n=======\nother\n>>>>>>> theirs')
        errors = io.StringIO()
        with redirect_stderr(errors):
            self.assertEqual(main(['--repo', str(self.root), 'sync']), 1)
        self.assertNotIn('Traceback', errors.getvalue())
        self.assertEqual((self.binary.read_bytes(), Stamp.read(self.binary)), before)
