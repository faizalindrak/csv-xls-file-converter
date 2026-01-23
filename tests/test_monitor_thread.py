# tests/test_monitor_thread.py
import pytest
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, '.')


# Mock all GUI dependencies before importing
with patch.dict('sys.modules', {
    'qfluentwidgets': Mock(),
    'PyQt6.QtCore': Mock(),
    'PyQt6.QtWidgets': Mock(),
    'PyQt6.QtGui': Mock(),
}):
    from gui import MonitorThread


def test_monitor_thread_accepts_file_formats():
    """MonitorThread should accept file_formats parameter"""
    thread = MonitorThread(
        folder_path="/tmp/test",
        output_folder=None,
        delete_source=False,
        process_existing=False,
        auto_detect_dates=False,
        file_formats=['csv']
    )
    assert thread.file_formats == ['csv']


def test_monitor_thread_defaults_to_both_formats():
    """MonitorThread should default to both csv and xls"""
    thread = MonitorThread(
        folder_path="/tmp/test",
        output_folder=None,
        delete_source=False,
        process_existing=False
    )
    assert thread.file_formats == ['csv', 'xls']
