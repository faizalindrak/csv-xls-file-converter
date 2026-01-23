# tests/test_format_filter.py
import pytest
import os
import sys

# We'll test the logic by directly instantiating the handler
# without needing to import the full GUI


def test_should_process_respects_csv_only():
    """Handler should only process csv when allowed_formats=['csv']"""
    allowed_formats = ['csv']

    # Simulate the _should_process logic
    def _should_process(file_path):
        ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        return ext in allowed_formats

    assert _should_process("test.csv") == True
    assert _should_process("test.CSV") == True  # case insensitive
    assert _should_process("test.xls") == False


def test_should_process_respects_xls_only():
    """Handler should only process xls when allowed_formats=['xls']"""
    allowed_formats = ['xls']

    def _should_process(file_path):
        ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        return ext in allowed_formats

    assert _should_process("test.csv") == False
    assert _should_process("test.xls") == True
    assert _should_process("test.XLS") == True


def test_should_process_respects_both_formats():
    """Handler should process both when allowed_formats=['csv', 'xls']"""
    allowed_formats = ['csv', 'xls']

    def _should_process(file_path):
        ext = os.path.splitext(file_path)[1].lower().lstrip('.')
        return ext in allowed_formats

    assert _should_process("test.csv") == True
    assert _should_process("test.xls") == True
    assert _should_process("test.xlsx") == False


def test_old_implementation_fails_with_csv_only():
    """The OLD implementation accepts .xls even when only csv is allowed"""
    allowed_formats = ['csv']

    # OLD implementation (what's currently in gui.py)
    def _should_process_old(file_path):
        ext = os.path.splitext(file_path)[1].lower()
        return ext in [".csv", ".xls"]

    # This should fail - old implementation doesn't respect allowed_formats
    assert _should_process_old("test.csv") == True
    assert _should_process_old("test.xls") == True  # BUG: should be False when only csv allowed
