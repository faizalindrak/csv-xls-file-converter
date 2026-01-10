"""
Windows Context Menu Registration for CSV/XLS to XLSX Converter.

Handles registration and unregistration of Windows Explorer context menu entries
for .csv and .xls files. Supports both Windows 10 (classic) and Windows 11 (modern)
context menu styles.

Windows 11 uses a new context menu system that requires additional registry entries
to show custom commands in the top-level menu instead of "Show more options".
"""

import sys
import os
import ctypes

# Registry paths for context menu
# Classic context menu (Windows 10 style, also works in Win11 "Show more options")
SHELL_EXTENSIONS = {
    ".csv": r"Software\Classes\.csv\shell\ConvertToXLSX",
    ".xls": r"Software\Classes\.xls\shell\ConvertToXLSX",
}

# Windows 11 modern context menu uses a different approach
# We need to register under the file type's ProgID or use Shell Extensions
WIN11_SHELL_EXTENSIONS = {
    ".csv": r"Software\Classes\SystemFileAssociations\.csv\shell\ConvertToXLSX",
    ".xls": r"Software\Classes\SystemFileAssociations\.xls\shell\ConvertToXLSX",
}


def is_admin() -> bool:
    """Check if the current process has administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def get_executable_path() -> str:
    """Get the path to the current executable or script."""
    if getattr(sys, "frozen", False):
        # Running as compiled executable (PyInstaller)
        return sys.executable
    else:
        # Running as script - use pythonw to avoid console window
        python_exe = sys.executable
        script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "file_converter.py")
        )
        return f'"{python_exe}" "{script_path}"'


def get_command_string() -> str:
    """Get the command string to execute for context menu action."""
    if getattr(sys, "frozen", False):
        # Running as compiled executable
        exe_path = sys.executable
        return f'"{exe_path}" --silent "%1"'
    else:
        # Running as script
        python_exe = sys.executable
        script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "file_converter.py")
        )
        return f'"{python_exe}" "{script_path}" --silent "%1"'


def register_context_menu() -> tuple[bool, str]:
    """
    Register context menu entries for .csv and .xls files.

    Returns:
        Tuple of (success: bool, message: str)
    """
    if sys.platform != "win32":
        return False, "Context menu registration is only available on Windows"

    try:
        import winreg

        command = get_command_string()
        menu_text = "Convert to XLSX"
        icon_path = ""

        # Get icon path if running as executable
        if getattr(sys, "frozen", False):
            icon_path = sys.executable

        registered_count = 0

        # Register for both classic and Windows 11 style menus
        all_extensions = list(SHELL_EXTENSIONS.items()) + list(
            WIN11_SHELL_EXTENSIONS.items()
        )

        for ext, reg_path in all_extensions:
            try:
                # Create the shell command key
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_path)

                # Set the display name
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, menu_text)

                # Set icon (optional, uses exe icon)
                if icon_path:
                    winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon_path)

                # Promote into top-level menu (works for both Win10 and Win11)
                winreg.SetValueEx(key, "Position", 0, winreg.REG_SZ, "Top")

                winreg.CloseKey(key)

                # Create the command subkey
                command_key = winreg.CreateKey(
                    winreg.HKEY_CURRENT_USER, f"{reg_path}\\command"
                )
                winreg.SetValueEx(command_key, "", 0, winreg.REG_SZ, command)
                winreg.CloseKey(command_key)

                registered_count += 1
            except Exception as e:
                print(f"Warning: Failed to register for {ext}: {e}")

        if registered_count > 0:
            return True, f"Context menu registered for {registered_count} file types"
        else:
            return False, "Failed to register context menu for any file type"

    except ImportError:
        return False, "winreg module not available"
    except Exception as e:
        return False, f"Failed to register context menu: {e}"


def unregister_context_menu() -> tuple[bool, str]:
    """
    Unregister context menu entries for .csv and .xls files.

    Returns:
        Tuple of (success: bool, message: str)
    """
    if sys.platform != "win32":
        return False, "Context menu unregistration is only available on Windows"

    try:
        import winreg

        removed_count = 0

        # Unregister from both classic and Windows 11 style menus
        all_extensions = list(SHELL_EXTENSIONS.items()) + list(
            WIN11_SHELL_EXTENSIONS.items()
        )

        for ext, reg_path in all_extensions:
            try:
                # Delete the command subkey first
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{reg_path}\\command")
                except FileNotFoundError:
                    pass

                # Delete the main key
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, reg_path)
                    removed_count += 1
                except FileNotFoundError:
                    pass

            except Exception as e:
                print(f"Warning: Failed to unregister for {ext}: {e}")

        if removed_count > 0:
            return True, f"Context menu unregistered for {removed_count} file types"
        else:
            return True, "Context menu was not registered"

    except ImportError:
        return False, "winreg module not available"
    except Exception as e:
        return False, f"Failed to unregister context menu: {e}"


def is_context_menu_registered() -> bool:
    """
    Check if context menu is currently registered.

    Returns:
        True if at least one extension has context menu registered
    """
    if sys.platform != "win32":
        return False

    try:
        import winreg

        # Check any of the registration paths
        all_paths = list(SHELL_EXTENSIONS.values()) + list(
            WIN11_SHELL_EXTENSIONS.values()
        )
        for reg_path in all_paths:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path)
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                continue
            except Exception:
                continue

        return False

    except ImportError:
        return False
    except Exception:
        return False


def show_windows_notification(
    title: str, message: str, icon_type: str = "info"
) -> bool:
    """
    Show a Windows toast notification.

    Args:
        title: Notification title
        message: Notification body text
        icon_type: One of 'info', 'warning', 'error'

    Returns:
        True if notification was shown successfully
    """
    if sys.platform != "win32":
        return False

    try:
        # Try using win10toast if available
        try:
            from win10toast import ToastNotifier

            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=5, threaded=True)
            return True
        except ImportError:
            pass

        # Fallback: Use Windows balloon notification via ctypes
        # This is a simplified approach that works without external dependencies
        try:
            from ctypes import windll, create_unicode_buffer, byref
            from ctypes.wintypes import DWORD

            # Use powershell to show toast notification
            import subprocess

            # Escape quotes in message
            safe_title = title.replace('"', '`"').replace("'", "`'")
            safe_message = message.replace('"', '`"').replace("'", "`'")

            # PowerShell command to show toast notification
            ps_script = f"""
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

            $template = @"
            <toast>
                <visual>
                    <binding template="ToastText02">
                        <text id="1">{safe_title}</text>
                        <text id="2">{safe_message}</text>
                    </binding>
                </visual>
            </toast>
"@

            $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
            $xml.LoadXml($template)
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("CSV-XLS Converter").Show($toast)
            """

            # Run PowerShell in hidden mode
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE

            subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=10,
            )
            return True

        except Exception as e:
            print(f"Toast notification failed: {e}")
            return False

    except Exception as e:
        print(f"Failed to show notification: {e}")
        return False


if __name__ == "__main__":
    # Command line interface for testing
    import argparse

    parser = argparse.ArgumentParser(
        description="Manage Windows context menu registration"
    )
    parser.add_argument(
        "action", choices=["register", "unregister", "status"], help="Action to perform"
    )
    args = parser.parse_args()

    if args.action == "register":
        success, message = register_context_menu()
        print(f"{'Success' if success else 'Failed'}: {message}")
    elif args.action == "unregister":
        success, message = unregister_context_menu()
        print(f"{'Success' if success else 'Failed'}: {message}")
    elif args.action == "status":
        registered = is_context_menu_registered()
        print(f"Context menu is {'registered' if registered else 'not registered'}")
