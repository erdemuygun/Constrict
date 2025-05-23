from gi.repository import Adw, Gtk, Gio
from constrict.constrict_utils import get_encode_settings
from constrict.enums import QueuedVideoState
import subprocess

@Gtk.Template(resource_path='/com/github/wartybix/Constrict/queued_video_row.ui')
class QueuedVideoRow(Adw.ActionRow):
    __gtype_name__ = 'QueuedVideoRow'

    thumbnail = Gtk.Template.Child()
    progress_bar = Gtk.Template.Child()
    status_label = Gtk.Template.Child()
    menu_button = Gtk.Template.Child()

    # TODO: investigate window becoming blank?

    def __init__(
        self,
        video_path,
        display_name,
        width,
        height,
        fps,
        duration,
        target_size,
        fps_mode,
        **kwargs
    ):
        super().__init__(**kwargs)

        self.video_path = video_path
        self.display_name = display_name
        self.height = height
        self.width = width
        self.fps = fps
        self.duration = duration

        self.set_title(display_name)
        self.set_preview(target_size, fps_mode)

        # set thumbnail
        subprocess.run(['totem-video-thumbnailer', video_path, 'thumb.jpg'])
        self.thumbnail.set_from_file('thumb.jpg')

    def set_preview(self, target_size, fps_mode):
        encode_settings = get_encode_settings(
            target_size,
            fps_mode,
            self.width,
            self.height,
            self.fps,
            self.duration
        )

        if not encode_settings:
            return

        _, _, target_pixels, target_fps = encode_settings

        src_pixels = self.height if self.height > self.width else self.width

        # TODO: Remember, change this for RTL.
        subtitle = f'{src_pixels}p@{self.fps} → {target_pixels}p@{target_fps}'

        self.set_subtitle(subtitle)

    def set_state(self, state):
        is_compressing = state == QueuedVideoState.COMPRESSING
        is_complete = state == QueuedVideoState.COMPLETE

        # TODO: clear 'complete' label when compression settings change
        if is_compressing:
            self.progress_bar.set_fraction(0.0)

        self.progress_bar.set_visible(is_compressing)
        self.status_label.set_visible(is_complete)
        self.action_set_enabled('row.remove', not is_compressing)

    def set_progress_text(self, label):
        self.progress_bar.set_text(label)

    def get_progress_text(self):
        return self.progress_bar.get_text()

    def pulse_progress(self):
        self.progress_bar.pulse()

    def set_progress_fraction(self, fraction):
        self.progress_bar.set_fraction(fraction)
