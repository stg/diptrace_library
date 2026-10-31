"""Installed integration: selection, setup boundaries and owned artifacts."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from . import test_git as fixtures
from ..__main__ import main
from ..config import CONFIG, LEGACY, SIGNATURE, load_config
from ..files import Stamp, json_bytes
from ..locking import internal_commands
from ..setup import change_selection, install, uninstall
from ..sync import candidates, synchronize
from .. import sync as engine
from lib import ConversionNotice


class InstallationTests(unittest.TestCase):
    setUp = fixtures.GitTests.setUp
    export = fixtures.GitTests.export
    commit = fixtures.GitTests.commit
    edit_text = fixtures.GitTests.edit_text
    value = fixtures.GitTests.value

    def snapshot(self, path):
        return path.read_bytes(), Stamp.read(path)

    def test_pathspec_groups_and_ordered_disable_enable(self):
        directory = self.root / 'archive'
        directory.mkdir()
        for name in ('keep', 'skip'):
            (directory / (name + '.dch')).write_bytes(fixtures.design())
        change_selection(self.repo, ['*'], enabled=False)
        change_selection(self.repo, [':(glob)**/*.dch', ':(exclude)archive/skip.dch'], enabled=True)
        names = candidates(self.repo)
        self.assertEqual(self.repo.selected(names, load_config(self.repo)['rules']),
                         {'design.dch', 'archive/keep.dch'})
        change_selection(self.repo, [':(top,literal)design.dch'], enabled=False)
        self.assertEqual(self.repo.selected(names, load_config(self.repo)['rules']), {'archive/keep.dch'})
        change_selection(self.repo, [':(top,literal)design.dch'], enabled=True)
        self.export()
        self.assertTrue(self.text.exists())
        self.assertFalse((directory / 'skip.dch.git.xml').exists())

    def test_disable_keeps_files_and_stops_filter_ownership(self):
        self.export()
        change_selection(self.repo, ['*.dch'], enabled=False)
        self.text.write_bytes(b'user changes while disabled')
        before = self.snapshot(self.binary), self.snapshot(self.text), self.snapshot(self.metadata)
        self.repo.run('add', '--all')
        self.assertEqual((self.snapshot(self.binary), self.snapshot(self.text), self.snapshot(self.metadata)), before)
        self.assertTrue(self.metadata.exists())

    def test_enable_untracks_native_without_removing_local_file(self):
        self.repo.run('add', '-f', '--', self.binary.name)
        before = self.snapshot(self.binary)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--repo', str(self.root), 'enable', '--untrack', '*.dch']), 0)
        self.assertEqual(self.snapshot(self.binary), before)
        self.assertNotIn(self.binary.name, self.repo.names('ls-files', '--cached'))
        self.assertTrue(self.text.exists())

    def test_existing_monitor_is_not_overwritten(self):
        uninstall(self.repo)
        self.repo.run('config', 'core.fsmonitor', './existing-monitor')
        with self.assertRaisesRegex(ValueError, 'cannot share'):
            install(self.repo)
        self.assertEqual(self.repo.config('core.fsmonitor'), './existing-monitor')
        self.assertIsNone(self.repo.config('alias.diptrace'))

    def test_per_worktree_hook_override_is_not_silently_ignored(self):
        uninstall(self.repo)
        self.repo.run('config', 'extensions.worktreeConfig', 'true')
        path = self.repo.git_path('config.worktree')
        original = b'[core]\n\thooksPath = .user-hooks\n'
        path.write_bytes(original)
        with self.assertRaisesRegex(ValueError, 'per-worktree override'):
            install(self.repo)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.repo.config('core.hooksPath'), '.user-hooks')
        self.assertIsNone(self.repo.config('alias.diptrace'))

    def test_settings_and_attribute_blocks_are_restored(self):
        uninstall(self.repo)
        attributes = self.root / '.gitattributes'
        original = b'*.custom diff\n# user attributes\n'
        attributes.write_bytes(original)
        self.repo.run('config', 'core.fsmonitor', 'false')
        install(self.repo)
        self.assertTrue(attributes.read_bytes().startswith(original))
        self.assertIn(b'filter=diptrace', attributes.read_bytes())
        uninstall(self.repo)
        self.assertEqual(attributes.read_bytes(), original)
        self.assertEqual(self.repo.config('core.fsmonitor', local=True), 'false')
        for key in ('alias.diptrace', 'core.fsmonitorHookVersion', 'filter.diptrace.clean',
                    'filter.diptrace.smudge', 'filter.diptrace.required'):
            self.assertIsNone(self.repo.config(key, local=True))

    def test_user_change_after_installation_is_preserved(self):
        self.repo.run('config', 'filter.diptrace.clean', 'cat')
        with self.assertRaisesRegex(ValueError, 'changed since installation'):
            uninstall(self.repo)
        self.assertEqual(self.repo.config('filter.diptrace.clean'), 'cat')

    def incomplete_installation(self):
        uninstall(self.repo)
        original = self.repo.run
        def denied(*args, **kwargs):
            if args[:3] == ('config', '--local', 'core.fsmonitor') and len(args) == 4:
                raise ValueError('permission denied while updating config')
            return original(*args, **kwargs)
        with patch.object(self.repo, 'run', side_effect=denied):
            with self.assertRaisesRegex(OSError, 'rerun init or uninstall'):
                install(self.repo)

    def test_incomplete_setup_can_resume_without_changing_native(self):
        before = self.snapshot(self.binary)
        self.incomplete_installation()
        record = self.repo.common_dir / 'diptrace-git/installation.json'
        self.assertTrue(json.loads(record.read_text())['pending'])
        install(self.repo)
        self.assertFalse(json.loads(record.read_text())['pending'])
        self.assertEqual(self.snapshot(self.binary), before)

    def test_incomplete_setup_can_be_uninstalled(self):
        before = self.snapshot(self.binary)
        self.incomplete_installation()
        uninstall(self.repo)
        self.assertIsNone(self.repo.config('alias.diptrace'))
        self.assertIsNone(self.repo.config('core.fsmonitor'))
        self.assertEqual(self.snapshot(self.binary), before)

    def test_unlisted_user_hook_is_forwarded(self):
        uninstall(self.repo)
        directory = self.root / '.existing-hooks'
        directory.mkdir()
        hook = directory / 'post-commit'
        contents = b'#!/bin/sh\nprintf called > post-commit-called\n'
        hook.write_bytes(contents)
        hook.chmod(hook.stat().st_mode | 0o111)
        self.repo.run('config', 'core.hooksPath', '.existing-hooks')
        install(self.repo)
        self.commit()
        self.assertTrue((self.root / 'post-commit-called').exists())
        self.assertEqual(hook.read_bytes(), contents)
        uninstall(self.repo)
        self.assertEqual(self.repo.config('core.hooksPath'), '.existing-hooks')

    def legacy_pair(self):
        self.export()
        uninstall(self.repo)
        data = self.text.read_bytes()
        old = self.root / 'design.dchxml'
        self.text.replace(old)
        value = json.loads(self.metadata.read_text())
        value['format'] = LEGACY
        value['text']['path'] = old.name
        self.metadata.write_bytes(json_bytes(value))
        config = {'format': LEGACY, 'text_format': 'dchxml', 'rules': ['*.dch'], 'fallback_earlier': False}
        (self.root / CONFIG).write_bytes(json_bytes(config))
        return old, data

    def test_legacy_migration_preserves_native_and_text_data(self):
        old, data = self.legacy_pair()
        original = self.snapshot(self.binary)
        with self.assertRaisesRegex(ValueError, 'init --migrate'):
            install(self.repo)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--repo', str(self.root), 'init', '--migrate']), 0)
        self.assertEqual(self.snapshot(self.binary), original)
        self.assertEqual(self.text.read_bytes(), data)
        self.assertFalse(old.exists())
        self.assertEqual(json.loads(self.metadata.read_text())['format'], SIGNATURE)
        self.assertEqual(load_config(self.repo)['rules'][0]['pathspecs'], [':(top,literal)design.dch'])

    def test_migration_collision_fails_before_mutating_files(self):
        old, data = self.legacy_pair()
        self.text.write_bytes(b'an existing destination')
        before = {p: p.read_bytes() for p in (old, self.text, self.metadata, self.root / CONFIG, self.binary)}
        with self.assertRaisesRegex(ValueError, 'destination exists'):
            install(self.repo, migrate_legacy=True)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_missing_single_artifact_requires_and_accepts_explicit_regeneration(self):
        self.export()
        original = self.snapshot(self.binary)
        for path, message in ((self.metadata, 'missing reconstruction settings'),
                              (self.text, 'missing companion')):
            path.unlink()
            with self.assertRaisesRegex(ValueError, message):
                self.export()
            self.export(direction='binary', force=True, files=[self.binary.name])
            self.assertTrue(path.exists())
            self.assertEqual(self.snapshot(self.binary), original)

    def test_partial_batch_keeps_diagnostics_from_completed_conversion(self):
        (self.root / 'zz-broken.dch').write_bytes(b'broken input')
        original = engine.serialize
        def with_notice(document, **options):
            options['report'].notices.append(ConversionNotice(
                rule='test-warning', destination=options['format'],
                message='completed conversion warning', severity='warning'))
            return original(document, **options)
        errors, output = io.StringIO(), io.StringIO()
        with patch.object(engine, 'serialize', side_effect=with_notice), redirect_stderr(errors), redirect_stdout(output):
            self.assertEqual(main(['--repo', str(self.root), 'sync']), 1)
        self.assertIn('completed conversion warning', errors.getvalue())
        self.assertIn('Error:', errors.getvalue())
        self.assertIn('export design.dch', output.getvalue())
        self.assertTrue(self.text.exists())

    def test_unavailable_component_and_pattern_families_report_library_identity(self):
        change_selection(self.repo, ['*'], enabled=False)
        for native, family in (('eli', 'component'), ('lib', 'pattern')):
            source = self.root / ('unavailable.' + native)
            source.write_bytes(b'unavailable family fixture')
            for fmt in ('asc', 'xml'):
                config = load_config(self.repo)
                config['text_format'] = fmt
                config['rules'] = [{'pathspecs': [source.name], 'enabled': True}]
                (self.root / CONFIG).write_bytes(json_bytes(config))
                before = self.snapshot(source)
                errors = io.StringIO()
                with redirect_stderr(errors), redirect_stdout(io.StringIO()):
                    self.assertEqual(main(['--repo', str(self.root), 'sync']), 1)
                self.assertIn(family, errors.getvalue())
                self.assertIn(native, errors.getvalue())
                self.assertEqual(self.snapshot(source), before)
                self.assertFalse((self.root / (source.name + '.git.json')).exists())

    def pcb_git_workflow(self, text_format):
        from lib import ConversionReport, input_identity, read, serialize
        from lib.pcb import new_document, new_component

        # Each test owns a disposable repository. Replace its schematic fixture
        # with a board whose older output version must survive reconstruction.
        self.binary.unlink()
        install(self.repo, text_format=text_format)
        change_selection(self.repo, ['*'], enabled=False)
        binary = self.root / 'board.dip'
        text = self.root / ('board.dip.git.' + text_format)
        metadata = self.root / 'board.dip.git.json'
        document = new_document()
        part = document.one('/Board/Components').append(new_component('Resistor', 'R1'))
        part['Value'] = '10k'
        binary.write_bytes(serialize(document, format='dip', version=54, report=ConversionReport()))
        original = self.snapshot(binary)
        change_selection(self.repo, ['*.dip'], enabled=True)
        self.export()  # The enable command exports existing selected designs.

        def value(path):
            current = read(path, report=ConversionReport())
            return current.one('/Board/Components/Component[RefDes="R1"]')['Value']

        self.commit('track PCB companions')
        first = self.repo.run('rev-parse', 'HEAD').decode().strip()
        self.assertEqual(self.snapshot(binary), original)
        self.assertEqual(value(text), '10k')
        self.assertEqual(json.loads(metadata.read_text())['binary']['version'], 54)
        self.assertNotIn(binary.name, self.repo.names('ls-files', '--cached'))

        # A normal Git commit must notice a native-only change and refresh the
        # already tracked companion. No diptrace-specific commit command runs.
        part['Value'] = '22k'
        binary.write_bytes(serialize(document, format='dip', version=54, report=ConversionReport()))
        edited = self.snapshot(binary)
        self.repo.run('commit', '-qam', 'edit PCB value')
        second = self.repo.run('rev-parse', 'HEAD').decode().strip()
        self.assertNotEqual(first, second)
        self.assertEqual(value(text), '22k')
        self.assertEqual(self.snapshot(binary), edited)

        for revision, expected in ((first, '10k'), (second, '22k')):
            self.repo.run('checkout', '-q', revision)
            self.assertEqual(value(binary), expected)
            self.assertEqual(input_identity(binary.read_bytes()).version, 54)
            before_status = self.snapshot(binary)
            self.repo.run('status', '--porcelain')
            self.assertEqual(self.snapshot(binary), before_status)

    def test_pcb_xml_native_edits_and_checkout_use_recorded_version(self):
        self.pcb_git_workflow('xml')

    def test_pcb_asc_native_edits_and_checkout_use_recorded_version(self):
        self.pcb_git_workflow('asc')

    def test_user_exports_and_leading_dash_filename(self):
        for name in ('design.xml', 'design.asc', 'design.dchxml'):
            (self.root / name).write_bytes(b'user-owned export')
        source = self.root / '-extra.dch'
        source.write_bytes(fixtures.design('33k'))
        self.commit()
        self.assertTrue((self.root / '-extra.dch.git.xml').exists())
        for name in ('design.xml', 'design.asc', 'design.dchxml'):
            self.assertEqual((self.root / name).read_bytes(), b'user-owned export')

    def test_repeated_clone_setup_preserves_committed_settings_and_artifacts(self):
        settings = self.root / CONFIG
        config = load_config(self.repo)
        settings.write_text(json.dumps(config, indent=4) + '\n')
        self.commit()
        target = self.folder / 'cloned project'
        subprocess.run(['git', 'clone', '-q', str(self.root), str(target)], check=True)
        files = [target / CONFIG, target / self.text.name, target / self.metadata.name]
        originals = {p: self.snapshot(p) for p in files}
        for _ in range(2):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main(['--repo', str(target), 'init']), 0)
        self.assertEqual(self.value(target / self.binary.name), '10k')
        for path, before in originals.items():
            self.assertEqual(self.snapshot(path), before)

    def test_historical_filtered_read_has_no_native_side_effect(self):
        self.commit()
        first = self.repo.run('rev-parse', 'HEAD').decode().strip()
        self.binary.write_bytes(fixtures.design('22k'))
        self.repo.run('commit', '-qam', 'next design')
        before = self.snapshot(self.binary), self.snapshot(self.text)
        self.repo.run('cat-file', '--filters', first + ':' + self.text.name)
        self.assertEqual((self.snapshot(self.binary), self.snapshot(self.text)), before)

    def test_outer_literal_pathspec_mode_does_not_hide_native_changes(self):
        self.commit()
        self.binary.write_bytes(fixtures.design('22k'))
        before = self.snapshot(self.binary)
        self.repo.run('--literal-pathspecs', 'commit', '-qam', 'native under literal mode')
        self.assertEqual(self.value(self.text), '22k')
        self.assertEqual(self.snapshot(self.binary), before)
