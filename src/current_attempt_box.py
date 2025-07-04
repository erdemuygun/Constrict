# current_attempt_box.py
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

from gi.repository import Adw, Gtk, GLib
from constrict.shared import update_ui

@Gtk.Template(resource_path='/com/github/wartybix/Constrict/current_attempt_box.ui')
class CurrentAttemptBox(Gtk.Box):
    __gtype_name__ = "CurrentAttemptBox"

    progress_bar = Gtk.Template.Child()
    attempt_label = Gtk.Template.Child()
    target_details_label = Gtk.Template.Child()
    progress_details_label = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def set_progress_text(self, label, daemon):
        update_ui(self.progress_details_label.set_text, label, daemon)

    def get_progress_text(self):
        return self.progress_bar.get_text()

    def pulse_progress(self, daemon):
        update_ui(self.progress_bar.pulse, None, False)

    def set_attempt_details(
        self,
        attempt_no,
        vid_bitrate,
        vid_height,
        vid_fps,
        daemon
    ):
        # TRANSLATORS: {} represents the attempt number.
        attempt_no_label = _('Attempt {}').format(str(attempt_no))
        update_ui(self.attempt_label.set_label, attempt_no_label, daemon)

        # TRANSLATORS: the first {} represents a bitrate value (e.g. '50 Kbps')
        # The second {} represents details about the frame height and FPS
        # (e.g. '1080p@60')
        target_details_label = _('Compressing to {} ({})').format(
            f'{vid_bitrate // 1000} Kbps',
            f'{vid_height}p@{vid_fps}'
        )
        update_ui(
            self.target_details_label.set_label,
            target_details_label,
            daemon
        )

    def set_progress_fraction(self, fraction, daemon):
        update_ui(self.progress_bar.set_fraction, fraction, daemon)

        # TODO: add estimated time

        progress_text = f'{int(round(fraction * 100, 0))} %'
        update_ui(self.progress_details_label.set_label, progress_text, daemon)
