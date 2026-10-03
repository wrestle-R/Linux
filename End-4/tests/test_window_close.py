import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch


SPEC = importlib.util.spec_from_file_location("window_close", Path(__file__).resolve().parents[1] / "window-close.py")
close = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(close)


class WindowCloseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.environment = patch.dict(os.environ, {
            "XDG_RUNTIME_DIR": str(self.directory), "XDG_STATE_HOME": str(self.directory / "state"),
            "HYPRLAND_INSTANCE_SIGNATURE": "test-session",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.target = {"address": "0x123abc", "pid": 123, "stableId": 99, "mapped": True, "class": "Test"}

    def record(self, timestamp=1, app="Test"):
        return {"version": 1, "closed_at": timestamp, "app": app,
                "launch": {"kind": "argv", "argv": ["/missing/app"]}}

    def test_reused_address_does_not_select_a_new_window(self):
        reused = dict(self.target, stableId=100)
        with patch.object(close, "hypr", return_value=[reused]):
            self.assertIsNone(close.get_target("0x123abc", 123, 99))
            self.assertFalse(close.target_exists(self.target))

    def test_hyprctl_hex_identity_matches_lua_decimal_identity(self):
        raw = dict(self.target, stableId="18000002")
        with patch.object(close, "hypr", return_value=[raw]):
            target = close.get_target("0x123abc", 123, 0x18000002)
            self.assertEqual(target["stableId"], 0x18000002)
            self.assertTrue(close.target_exists(target))

    def test_invalid_address_never_reaches_compositor(self):
        with patch.object(close, "hypr") as command:
            with self.assertRaises(close.CloseError):
                close.get_target('0x1"; os.execute("bad")', 123, 99)
            command.assert_not_called()

    def test_atomic_close_contains_original_identity_and_no_title(self):
        target = dict(self.target, title='$(touch /tmp/unwanted)')
        with patch.object(close, "hypr", return_value="ok") as command:
            close.close_target(target)
            expression = command.call_args.args[1]
            self.assertIn('address:0x123abc', expression)
            self.assertIn('w.pid ~= 123', expression)
            self.assertIn('w.stable_id ~= 99', expression)
            self.assertNotIn('touch', expression)

    def test_repeated_open_keeps_one_dialog(self):
        with close.locked(close.runtime_dir() / "dialog.lock"):
            with patch.object(close, "get_target") as lookup:
                close.dialog("0x123abc", 123, 99)
                lookup.assert_not_called()

    def test_cancel_does_not_dispatch_or_change_history(self):
        events = Mock()
        with patch.object(close, "get_target", return_value=self.target), \
             patch.object(close, "launch_record", return_value=self.record()), \
             patch.object(close, "event_socket", return_value=events), \
             patch.object(close, "show_dialog", return_value=False), \
             patch.object(close, "close_target") as dispatch, \
             patch.object(close, "save_record") as save:
            close.dialog()
            dispatch.assert_not_called()
            save.assert_not_called()
            events.close.assert_called_once()

    def test_failed_close_does_not_replace_history(self):
        events = Mock()
        with patch.object(close, "get_target", return_value=self.target), \
             patch.object(close, "launch_record", return_value=self.record()), \
             patch.object(close, "event_socket", return_value=events), \
             patch.object(close, "show_dialog", return_value=True), \
             patch.object(close, "target_exists", return_value=True), \
             patch.object(close, "close_target", side_effect=close.CloseError("failed")), \
             patch.object(close, "save_record") as save:
            with self.assertRaises(close.CloseError):
                close.dialog()
            save.assert_not_called()

    def test_save_prompt_is_observed_until_the_window_closes(self):
        events = Mock()
        events.recv.return_value = b"closewindow>>123abc\n"
        with patch.object(close, "target_exists", side_effect=[True, False]), \
             patch.object(close.select, "select", return_value=([events], [], [])), \
             patch.object(close, "save_record") as save:
            close.remember_when_closed(self.target, self.record(), events, close.runtime_dir())
            save.assert_called_once()

    def test_compositor_disconnect_does_not_mark_an_open_app_closed(self):
        events = Mock()
        events.recv.return_value = b""
        with patch.object(close, "target_exists", return_value=True), \
             patch.object(close.select, "select", return_value=([events], [], [])), \
             patch.object(close, "save_record") as save:
            close.remember_when_closed(self.target, self.record(), events, close.runtime_dir())
            save.assert_not_called()

    def test_only_latest_close_is_kept_and_private(self):
        close.save_record(self.record(2, "Newer"))
        close.save_record(self.record(1, "Older"))
        destination = close.state_dir() / "last-closed.json"
        self.assertEqual(json.loads(destination.read_text())["app"], "Newer")
        self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        close.save_record(self.record(3, "Latest"))
        self.assertEqual(json.loads(destination.read_text())["app"], "Latest")

    def test_restore_consumes_one_entry_and_then_reports_empty(self):
        close.save_record(self.record())
        with patch.object(close, "launch_app") as launch, patch.object(close, "notify") as notify:
            close.restore()
            close.restore()
            launch.assert_called_once()
            notify.assert_called_once_with("No closed application to reopen.")
        self.assertFalse((close.state_dir() / "last-closed.json").exists())

    def test_failed_restore_keeps_the_entry(self):
        close.save_record(self.record())
        with patch.object(close, "launch_app", side_effect=close.CloseError("failed")):
            with self.assertRaises(close.CloseError):
                close.restore()
        self.assertTrue((close.state_dir() / "last-closed.json").exists())

    def test_concurrent_restore_cannot_launch_twice(self):
        close.save_record(self.record())
        with close.locked(close.runtime_dir() / "restore.lock"):
            with patch.object(close, "launch_app") as launch:
                close.restore()
                launch.assert_not_called()

    def profile(self, folders):
        profile = self.directory / "vscode-user-data"
        storage = profile / "User/globalStorage"
        storage.mkdir(parents=True)
        (self.directory / "vscode-extensions").mkdir()
        for folder in folders:
            folder.mkdir(parents=True, exist_ok=True)
        (storage / "storage.json").write_text(json.dumps({"windowsState": {
            "lastActiveWindow": {"folder": folders[0].as_uri()},
            "openedWindows": [{"folder": f.as_uri()} for f in folders],
        }}))
        process = {"argv": ["/usr/share/code/code", "--user-data-dir", str(profile)],
                   "exe": "/usr/share/code/code", "cwd": str(self.directory), "env": {}}
        return profile, process

    def test_vscode_restores_selected_project_and_profile(self):
        first, second = self.directory / "Alpha project", self.directory / "Beta"
        profile, process = self.profile([first, second])
        target = dict(self.target, title="file.py - Beta - Visual Studio Code")
        with patch.object(close.shutil, "which", return_value="/usr/bin/code"):
            launch = close.vscode_launch(target, process)
        self.assertEqual(launch["argv"], ["/usr/bin/code", "--new-window", "--user-data-dir", str(profile),
                                           "--extensions-dir", str(self.directory / "vscode-extensions"), str(second)])

    def test_vscode_ambiguous_project_does_not_guess(self):
        first, second = self.directory / "one/Same", self.directory / "two/Same"
        _, process = self.profile([first, second])
        target = dict(self.target, title="Welcome - Same - Visual Studio Code")
        launch = close.vscode_launch(target, process)
        self.assertNotIn(str(first), launch["argv"])
        self.assertNotIn(str(second), launch["argv"])
        self.assertNotIn("--new-window", launch["argv"])

    def test_vscode_new_project_can_use_workspace_metadata(self):
        project = self.directory / "New project"
        profile, process = self.profile([project])
        (profile / "User/globalStorage/storage.json").unlink()
        metadata = profile / "User/workspaceStorage/123/workspace.json"
        metadata.parent.mkdir(parents=True)
        metadata.write_text(json.dumps({"folder": project.as_uri()}))
        target = dict(self.target, title="Welcome - New project - Visual Studio Code")
        self.assertEqual(close.vscode_launch(target, process)["argv"][-1], str(project))

    def test_appimage_uses_original_path_and_literal_arguments(self):
        process = {"argv": ["/tmp/.mount_app/program", "a file $(literal).txt"],
                   "exe": "/tmp/.mount_app/program", "cwd": str(self.directory),
                   "env": {"APPIMAGE": "/home/test/app.AppImage"}}
        with patch.object(close, "process_info", return_value=process):
            record = close.launch_record(self.target)
        self.assertEqual(record["launch"]["argv"], ["/home/test/app.AppImage", "a file $(literal).txt"])


if __name__ == "__main__":
    unittest.main()
