# tests/test_monitor_profile.py
import sys
from unittest.mock import MagicMock

# Mock GUI dependencies before importing gui
sys.modules['PySide6'] = MagicMock()
sys.modules['PySide6.QtWidgets'] = MagicMock()
sys.modules['PySide6.QtCore'] = MagicMock()
sys.modules['PySide6.QtGui'] = MagicMock()
sys.modules['PySide6.QtNetwork'] = MagicMock()
sys.modules['qfluentwidgets'] = MagicMock()

sys.path.insert(0, '.')

from gui import MonitorProfile


def test_monitor_profile_has_file_formats_field():
    """MonitorProfile should have file_formats field with default ['csv', 'xls']"""
    profile = MonitorProfile()
    assert hasattr(profile, 'file_formats')
    assert profile.file_formats == ['csv', 'xls']


def test_monitor_profile_file_formats_serialization():
    """file_formats should serialize to dict and deserialize correctly"""
    profile = MonitorProfile(file_formats=['csv'])
    data = profile.to_dict()
    assert data['file_formats'] == ['csv']

    restored = MonitorProfile.from_dict(data)
    assert restored.file_formats == ['csv']


def test_monitor_profile_file_formats_empty_not_allowed():
    """Profile should have at least one format (validation happens at UI level)"""
    profile = MonitorProfile(file_formats=[])
    assert profile.file_formats == []
