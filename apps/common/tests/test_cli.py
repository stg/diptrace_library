"""Reports filter by severity without hiding progress or changing exit status."""
from contextlib import redirect_stderr, redirect_stdout
import io
import unittest

from lib import ConversionNotice, ConversionReport
from apps.common.cli import Console


class ConsoleTests(unittest.TestCase):
    def report(self):
        return ConversionReport([
            ConversionNotice('normalize', 'asc', 'normalized', severity='info', label='design.asc'),
            ConversionNotice('loss', 'asc', 'omitted', severity='warning'),
            ConversionNotice('failed', 'asc', 'cannot export', severity='error'),
        ])

    def test_default_threshold_and_streams(self):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            console = Console()
            console.report(self.report())
            console.info('Finished')
        self.assertEqual(output.getvalue(), 'Info: Finished\n')
        self.assertEqual(errors.getvalue(), 'Warning: omitted\nError: cannot export\n')

    def test_info_diagnostics_go_to_stdout_with_source_label(self):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            Console('info').report(self.report())
        self.assertEqual(output.getvalue(), 'Info: design.asc: normalized\n')
        self.assertIn('Warning: omitted', errors.getvalue())

    def test_error_threshold_still_reports_progress_and_failure_once(self):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            console = Console('error')
            console.info('Started')
            status = console.failure('conversion failed', ValueError('cannot export'), report=self.report())
        self.assertEqual(status, 1)
        self.assertEqual(output.getvalue(), 'Info: Started\n')
        self.assertEqual(errors.getvalue(), 'Error: conversion failed: cannot export\n')
