# source_popover_box.py
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
from constrict import PREFIX
from typing import Any


@Gtk.Template(resource_path=f'{PREFIX}/source_popover_box.ui')
class SourcePopoverBox(Gtk.Box):
    """ A box used in a GtkPopover to show details of a video's compression
    details """
    __gtype_name__ = "SourcePopoverBox"

    def __init__(self, top_widget: Gtk.Widget, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self.top_widget = top_widget
        self.prepend(self.top_widget)

    def set_top_widget(self, widget: Gtk.Widget, daemon: bool) -> None:
        """ Sets the widget to be shown at the top of the popover """
        update_ui(self.remove, self.top_widget, daemon)
        update_ui(self.prepend, widget, daemon)

        self.top_widget = widget

    def add_fail_widget(self, fail_widget: Gtk.Widget, daemon):
        """ Add a widget from when a compression fails to the popover """
        if daemon:
            GLib.idle_add(
                self.insert_child_after,
                fail_widget,
                self.top_widget
            )
        else:
            self.add_child_after(fail_widget, self.top_widget)
