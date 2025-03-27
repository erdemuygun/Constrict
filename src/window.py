# window.py
#
# Copyright 2025 Wartybix
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Adw, Gtk, Gio

@Gtk.Template(resource_path='/com/github/wartybix/Constrict/window.ui')
class ConstrictWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'ConstrictWindow'

    split_view = Gtk.Template.Child()
    export_button = Gtk.Template.Child()
    video_queue = Gtk.Template.Child()
    add_videos_button = Gtk.Template.Child()

    staged_videos = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        toggle_sidebar_action = Gio.SimpleAction(name="toggle-sidebar")
        toggle_sidebar_action.connect("activate", self.toggle_sidebar)
        self.add_action(toggle_sidebar_action)

        open_action = Gio.SimpleAction(name="open")
        open_action.connect("activate", self.open_file_dialog)
        self.add_action(open_action)

        export_action = Gio.SimpleAction(name="export")
        export_action.connect("activate", self.export)
        self.add_action(export_action)

    def open(self, action, _):
        print("Open action run")

    def export(self, action, _):
        print("Export action run")

    def toggle_sidebar(self, action, _):
        sidebar_shown = self.split_view.get_show_sidebar()
        self.split_view.set_show_sidebar(not sidebar_shown)

    def open_file_dialog(self, action, parameter):
        # Create new file selection dialog, using "open" mode
        native = Gtk.FileDialog()
        native.open_multiple(self, None, self.on_open_response)

    def on_open_response(self, dialog, result):
        files = dialog.open_multiple_finish(result)

        if not files:
            return

        self.video_queue.remove(self.add_videos_button)

        for video in files:
            # TODO: make async query?
            info = video.query_info('standard::display-name', Gio.FileQueryInfoFlags.NONE)
            display_name = info.get_display_name() if info else video.get_basename()
            print(f'{video.get_basename()} - {video.get_path()}')

            # TODO: Add thumbnail -- I think Nautilus generates one from a
            # frame 1/3 through the video

            action_row = Adw.ActionRow()
            action_row.set_title(display_name)

            self.video_queue.add(action_row)
            self.staged_videos.append(video.get_path())

        self.video_queue.add(self.add_videos_button)
        print(self.staged_videos)
