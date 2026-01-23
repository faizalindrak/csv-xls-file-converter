# tests/test_existing_files_filter.py
import pytest
import os
import tempfile
from pathlib import Path


DISCOVERY_CHUNK_SIZE = 100  # Same as in gui.py


def discover_files_lazy_old(folder_path, file_formats):
    """Old implementation with hardcoded patterns"""
    folder = Path(folder_path)
    chunk = []

    for pattern in ["**/*.csv", "**/*.xls"]:  # Hardcoded!
        try:
            for file_path in folder.glob(pattern):
                chunk.append(file_path)
                if len(chunk) >= DISCOVERY_CHUNK_SIZE:
                    yield chunk
                    chunk = []
        except Exception:
            pass

    if chunk:
        yield chunk


def discover_files_lazy_new(folder_path, file_formats):
    """New implementation using file_formats parameter"""
    folder = Path(folder_path)
    chunk = []

    for fmt in file_formats:
        pattern = f"**/*.{fmt}"
        try:
            for file_path in folder.glob(pattern):
                chunk.append(file_path)
                if len(chunk) >= DISCOVERY_CHUNK_SIZE:
                    yield chunk
                    chunk = []
        except Exception:
            pass

    if chunk:
        yield chunk


def test_discover_files_old_ignores_format_filter():
    """Old implementation ignores format filter (should find both csv and xls)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        open(os.path.join(tmpdir, "test1.csv"), 'w').close()
        open(os.path.join(tmpdir, "test2.xls"), 'w').close()
        open(os.path.join(tmpdir, "test3.txt"), 'w').close()

        # Even with CSV only filter, old version finds both
        files = []
        for chunk in discover_files_lazy_old(tmpdir, ['csv']):
            files.extend([str(f) for f in chunk])

        # Old implementation finds BOTH csv and xls (WRONG!)
        assert len(files) == 2, f"Old implementation should find 2 files, got {len(files)}"


def test_discover_files_new_respects_format_filter():
    """New implementation respects format filter"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files
        open(os.path.join(tmpdir, "test1.csv"), 'w').close()
        open(os.path.join(tmpdir, "test2.xls"), 'w').close()
        open(os.path.join(tmpdir, "test3.txt"), 'w').close()

        # CSV only
        files = []
        for chunk in discover_files_lazy_new(tmpdir, ['csv']):
            files.extend([str(f) for f in chunk])

        assert len(files) == 1, f"Expected 1 CSV file, got {len(files)}: {files}"
        assert files[0].endswith('.csv')

        # XLS only
        files2 = []
        for chunk in discover_files_lazy_new(tmpdir, ['xls']):
            files2.extend([str(f) for f in chunk])

        assert len(files2) == 1, f"Expected 1 XLS file, got {len(files2)}: {files2}"
        assert files2[0].endswith('.xls')

        # Both formats
        files3 = []
        for chunk in discover_files_lazy_new(tmpdir, ['csv', 'xls']):
            files3.extend([str(f) for f in chunk])

        assert len(files3) == 2, f"Expected 2 files, got {len(files3)}"
