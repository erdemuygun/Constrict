# sources_row.py
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

# Acknowledgements: a lot of the code for dragging and dropping rows to
# re-order them have been 'borrowed' from GNOME Settings and GNOME Music.
# Thank you to the GNOME Project for making the implementation of this in my
# own project less of a headache.
# - https://gitlab.gnome.org/GNOME/gnome-control-center/-/blob/4b53cd7cf99e0370be3c35a34e1d31155498ad84/panels/keyboard/cc-input-row.c
# - https://gitlab.gnome.org/GNOME/gnome-music/-/blob/a79f46a5d81cd48d26c55a6bf10fcd48c16e63ab/data/ui/SongWidget.ui
# - https://gitlab.gnome.org/GNOME/gnome-music/-/blob/a79f46a5d81cd48d26c55a6bf10fcd48c16e63ab/gnomemusic/widgets/songwidget.py

from gi.repository import Adw, Gtk, Gio, GLib, Gdk
from pathlib import Path
from constrict.shared import get_tmp_dir, update_ui
from constrict.constrict_utils import get_encode_settings, get_resolution, get_framerate, get_duration
from constrict.enums import SourceState, Thumbnailer
from constrict.progress_pie import ProgressPie
from constrict.attempt_fail_box import AttemptFailBox
from constrict.source_popover_box import SourcePopoverBox
import threading
import subprocess
import os


@Gtk.Template(resource_path='/io/github/wartybix/Constrict/sources_row.ui')
class SourcesRow(Adw.ActionRow):
    __gtype_name__ = 'SourcesRow'

    thumbnail = Gtk.Template.Child()
    menu_button = Gtk.Template.Child()
    drag_source = Gtk.Template.Child()
    error_icon = Gtk.Template.Child()
    progress_pie = Gtk.Template.Child()
    progress_spinner = Gtk.Template.Child()
    progress_button = Gtk.Template.Child()
    video_broken_button = Gtk.Template.Child()
    incompatible_button = Gtk.Template.Child()
    incompatible_label = Gtk.Template.Child()
    complete_button = Gtk.Template.Child()
    complete_label = Gtk.Template.Child()
    complete_popover = Gtk.Template.Child()
    drag_handle_revealer = Gtk.Template.Child()
    popover = Gtk.Template.Child()
    popover_scrolled_window = Gtk.Template.Child()

    # TODO: make set_preview async on update, not just in constructor

    def __init__(
        self,
        video_path,
        display_name,
        file_hash=None,
        target_size_getter=None,
        fps_mode_getter=None,
        error_action=lambda: None,
        warning_action=None,
        remove_action=lambda: None,
        **kwargs
    ):
        super().__init__(**kwargs)

        self.video_path = video_path
        self.display_name = display_name

        self.height = None
        self.width = None
        self.fps = None
        self.duration = None
        self.state = SourceState.PENDING
        self.error_details = ""
        self.error_action = error_action
        self.warning_action = warning_action
        self.remove_action = remove_action
        self.size = None
        self.compressed_path = None

        self.set_title(display_name)

        self.install_action('row.move-up', None, self.move_up)
        self.install_action('row.move-down', None, self.move_down)
        self.install_action('row.on-error', None, self.on_error_query)
        self.install_action(
            'row.find-compressed-file',
            None,
            self.find_compressed_file
        )
        self.install_action('row.remove', None, self.on_remove)

        if file_hash:
            thumb_thread = threading.Thread(
                target=self.set_thumbnail,
                args=[file_hash, True]
            )
            thumb_thread.daemon = True
            thumb_thread.start()

        if target_size_getter and fps_mode_getter:
            preview_thread = threading.Thread(
                target=self.set_preview,
                args=[target_size_getter, fps_mode_getter, True]
            )
            preview_thread.daemon = True
            preview_thread.start()

        self.drag_widget = None

        self.popover_box = None

    def initiate_popover_box(self, top_widget, daemon):
        self.popover_box = SourcePopoverBox(top_widget)
        update_ui(
            self.popover_scrolled_window.set_child,
            self.popover_box,
            daemon
        )

    def set_popover_top_widget(self, top_widget, daemon):
        if not self.popover_box:
            return

        self.popover_box.set_top_widget(top_widget, daemon)

    def add_attempt_fail(
        self,
        attempt_no,
        vid_bitrate,
        is_hq_audio,
        vid_height,
        vid_fps,
        compressed_size_bytes,
        target_size_bytes,
        daemon
    ):
        if not self.popover_box:
            return

        fail_box = AttemptFailBox(
            attempt_no,
            vid_bitrate,
            is_hq_audio,
            vid_height,
            vid_fps,
            compressed_size_bytes,
            target_size_bytes
        )
        self.popover_box.add_fail_widget(fail_box, daemon)

    def set_draggable(self, can_drag):
        propagation_phase = Gtk.PropagationPhase.CAPTURE if (
            can_drag
        ) else Gtk.PropagationPhase.NONE

        self.drag_source.set_propagation_phase(propagation_phase)

    @Gtk.Template.Callback()
    def on_drag_prepare(self, drag_source, x, y):
        self.drag_x = x
        self.drag_y = y

        return Gdk.ContentProvider.new_for_value(self)

    @Gtk.Template.Callback()
    def on_drag_begin(self, drag_source, drag):
        self.drag_widget = Gtk.ListBox.new()
        self.drag_widget.set_size_request(self.get_width(), -1)

        drag_row = SourcesRow(self.video_path, self.display_name)
        drag_row.set_subtitle(self.get_subtitle())
        drag_row.set_state(self.state, False)

        thumb_storage_type = self.thumbnail.get_storage_type()
        if thumb_storage_type == Gtk.ImageType.ICON_NAME:
            icon_name = self.thumbnail.get_icon_name()
            drag_row.thumbnail.set_from_icon_name(icon_name)
        elif thumb_storage_type == Gtk.ImageType.PAINTABLE:
            paintable = self.thumbnail.get_paintable()
            drag_row.thumbnail.set_from_paintable(paintable)

        self.drag_widget.append(drag_row)
        self.drag_widget.drag_highlight_row(drag_row)

        drag_icon = Gtk.DragIcon.get_for_drag(drag)
        drag_icon.set_child(self.drag_widget)
        drag.set_hotspot(self.drag_x, self.drag_y)

    @Gtk.Template.Callback()
    def on_motion(self, drop_target, x, y):
        row_to_drop = drop_target.get_value()
        source_list_box = row_to_drop.get_parent()
        this_list_box = self.get_parent()

        # Don't allow drop if source and target are not in the same list box.
        return Gdk.DragAction.MOVE if this_list_box == source_list_box else 0

    @Gtk.Template.Callback()
    def on_drop(self, drop_target, source_row, x, y):
        self.drag_widget = None
        self.drag_x = 0
        self.drag_y = 0

        source_position = source_row.get_index()
        target_position = self.get_index()
        if source_position == target_position:
            return False

        this_list_box = self.get_parent()
        source_list_box = source_row.get_parent()

        # Only allow re-arranging rows in the same window. I.e., do not allow
        # dragging of sources to the list box of another Constrict window.
        if this_list_box != source_list_box:
            return False

        this_list_box.move(source_row, self)

    def on_remove(self, sources_row, action_name, parameter):
        sources_row.remove_action(sources_row)

    def on_error_query(self, widget, action_name, parameter):
        widget.error_action(widget.display_name, widget.error_details)

    def get_resolution(self):
        if not self.width or not self.height:
            self.width, self.height = get_resolution(self.video_path)

        return (self.width, self.height)

    def get_fps(self):
        if not self.fps:
            self.fps = get_framerate(self.video_path)

        return self.fps

    def get_duration(self):
        if not self.duration:
            self.duration = get_duration(self.video_path)

        return self.duration

    def set_thumbnail(self, file_hash, daemon):
        bin_totem = 'totem-video-thumbnailer'
        bin_ffmpeg = 'ffmpegthumbnailer'

        # Check Totem thumbnailer is installed.
        # Use FFMPEG thumbnailer as a fallback.
        # Use video-x-generic icon as the fallback's fallback.

        totem_exists = GLib.find_program_in_path(bin_totem)
        thumbnailer = Thumbnailer.TOTEM

        if not totem_exists:
            ffmpeg_exists = GLib.find_program_in_path(bin_ffmpeg)
            thumbnailer = Thumbnailer.FFMPEG

            if not ffmpeg_exists:
                update_ui(
                    self.thumbnail.set_from_icon_name,
                    'video-x-generic',
                    daemon
                )
                return

        # Check tmp directory is available to write.
        tmp_dir = get_tmp_dir()

        print(f'temp dir: {tmp_dir}')

        if not tmp_dir:
            update_ui(
                self.thumbnail.set_from_icon_name,
                'video-x-generic',
                daemon
            )
            return

        thumb_file = str(tmp_dir / f'{file_hash}.jpg')

        print(thumb_file)

        if thumbnailer == Thumbnailer.TOTEM:
            subprocess.run([
                bin_totem,
                self.video_path,
                thumb_file
            ])
        elif thumbnailer == Thumbnailer.FFMPEG:
            subprocess.run([
                bin_ffmpeg,
                '-i',
                self.video_path,
                '-o',
                thumb_file
            ])
        else:
            raise Exception('Unknown thumbnailer set. Whoopsie daisies.')

        update_ui(self.thumbnail.set_from_file, thumb_file, daemon)

    def get_size(self):
        if self.size:
            return self.size

        self.size = os.stat(self.video_path).st_size
        return self.size

    def set_incompatible(self, incompatible_msg, daemon):
        update_ui(self.incompatible_label.set_label, incompatible_msg, daemon)
        self.set_state(SourceState.INCOMPATIBLE, daemon)

    def set_error(self, error_details, daemon):
        self.error_details = error_details
        self.set_state(SourceState.ERROR, daemon)

    def set_complete(self, compressed_video_path, compressed_size_mb, daemon):
        update_ui(
            self.complete_label.set_label,
            # TRANSLATORS: the {} represents a file size value in MB. Please
            # use U+202F narrow no-break space (' ') between value and unit.
            _('Video compressed to {} MB.').format(compressed_size_mb),
            daemon
        )
        self.compressed_path = compressed_video_path
        self.set_state(SourceState.COMPLETE, daemon)

    def refresh_state(self, video_bitrate, target_size, daemon):
        if self.state == SourceState.BROKEN:
            return
        elif self.get_size() < target_size * 1024 * 1024:
            size_mb = round(self.get_size() / 1024 / 1024, 1)
            self.set_incompatible(
                # TRANSLATORS: both {} represent integers.
                # Please use U+202F Narrow no-break space (' ') between value
                # and unit.
                _('Video file size ({file_size} MB) already meets the target size ({target} MB).')
                    .format(file_size = size_mb, target = target_size),
                daemon
            )
        # Why is this threshold much higher than the one in constrict_utils.py?
        # It's because compressing to such low bitrates will often require
        # multiple attempts that'll eventually bring the bitrate to below
        # 5 Kbps anyway. So, since it'll most likely fail anyway, this
        # increased threshold is a courtesy to prevent wasting the user's time.
        elif video_bitrate < 11000:
            self.set_incompatible(
                # TRANSLATORS: {} is a file size value in MB.
                # Please use U+202F Narrow no-break space (' ') between value and
                # unit.
                _('Target size ({} MB) is too low for this file.')
                    .format(target_size),
                daemon
            )
        else:
            self.set_state(SourceState.PENDING, daemon)

    def set_preview(self, target_size_getter, fps_mode_getter, daemon):
        if self.state == SourceState.BROKEN:
            return

        try:
            width, height = self.get_resolution()
            fps = self.get_fps()
            duration = self.get_duration()
        except subprocess.CalledProcessError:
            self.set_state(SourceState.BROKEN, daemon)
            return

        target_size = target_size_getter()
        fps_mode = fps_mode_getter()

        encode_settings = get_encode_settings(
            target_size,
            fps_mode,
            width,
            height,
            fps,
            duration
        )

        video_bitrate, _, target_pixels, target_fps = encode_settings

        self.refresh_state(video_bitrate, target_size, daemon)

        if self.state == SourceState.INCOMPATIBLE:
            update_ui(self.set_subtitle, '', daemon)
            return

        src_pixels = self.height if self.height < self.width else self.width

        src_label = f'{src_pixels}p@{self.fps}'
        dest_label = f'{target_pixels}p@{target_fps}'

        subtitle = f'{dest_label} ← {src_label}' if (
            self.get_direction() == Gtk.TextDirection.RTL
        ) else f'{src_label} → {dest_label}'

        update_ui(self.set_subtitle, subtitle, daemon)

    def set_state(self, state, daemon):
        # If new state and old state are the same:
        if state == self.state:
            return

        is_compressing = state == SourceState.COMPRESSING
        is_complete = state == SourceState.COMPLETE
        is_error = state == SourceState.ERROR
        is_broken = state == SourceState.BROKEN
        is_incompatible = state == SourceState.INCOMPATIBLE

        if (is_broken or is_incompatible) and self.warning_action:
            self.warning_action(True, daemon)

        update_ui(self.progress_button.set_visible, is_compressing, daemon)
        update_ui(self.complete_button.set_visible, is_complete, daemon)
        update_ui(self.error_icon.set_visible, is_error, daemon)
        update_ui(self.video_broken_button.set_visible, is_broken, daemon)
        update_ui(
            self.incompatible_button.set_visible,
            is_incompatible,
            daemon
        )

        self.state = state

    def enable_spinner(self, enable_spinner, daemon):
        update_ui(self.progress_pie.set_visible, not enable_spinner, daemon)
        update_ui(self.progress_spinner.set_visible, enable_spinner, daemon)

    def show_drag_handle(self, shown):
        self.drag_handle_revealer.set_reveal_child(shown)

    def find_compressed_file(self, row, action_name, parameter):
        row.complete_popover.popdown()
        compressed_file = Gio.File.new_for_path(row.compressed_path)
        file_launcher = Gtk.FileLauncher.new(compressed_file)
        file_launcher.open_containing_folder()

    def move_up(self, row, action_name, parameter):
        list_box = row.get_parent()
        prev_index = row.get_index() - 1
        prev_row = list_box.get_row_at_index(prev_index)

        if not prev_row:
            print('previous row doesn\'t exist!')
            return

        list_box.move(row, prev_row)

    def move_down(self, row, action_name, parameter):
        list_box = row.get_parent()
        next_index = row.get_index() + 1
        next_row = list_box.get_row_at_index(next_index)

        if not next_row or next_row == list_box.add_videos_button:
            if not next_row:
                print('next_row doesn\'t exist!')
            elif next_row == list_box.add_videos_button:
                print('next row is add videos button!')

            return

        list_box.move(row, next_row)



