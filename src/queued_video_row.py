from gi.repository import Adw, Gtk, Gio
from constrict.constrict_utils import get_encode_settings, get_resolution, get_framerate, get_duration
from constrict.enums import QueuedVideoState
import threading
import subprocess

@Gtk.Template(resource_path='/com/github/wartybix/Constrict/queued_video_row.ui')
class QueuedVideoRow(Adw.ActionRow):
    __gtype_name__ = 'QueuedVideoRow'

    thumbnail = Gtk.Template.Child()
    progress_bar = Gtk.Template.Child()
    status_label = Gtk.Template.Child()
    menu_button = Gtk.Template.Child()

    # TODO: investigate window becoming blank?
    # TODO: input validation against adding corrupt videos
    # TODO: check for source video file being updated/removed post-queue?

    def __init__(
        self,
        video_path,
        display_name,
        target_size_getter,
        fps_mode_getter,
        **kwargs
    ):
        super().__init__(**kwargs)

        self.video_path = video_path
        self.display_name = display_name

        self.height = None
        self.width = None
        self.fps = None
        self.duration = None
        self.state = QueuedVideoState.PENDING

        self.set_title(display_name)

        # TODO: add catch for thumbnailer, use video mimetype icon as fallback

        # set thumbnail
        thumb_thread = threading.Thread(target=self.set_thumbnail)
        thumb_thread.daemon = True
        thumb_thread.start()

        preview_thread = threading.Thread(
            target=self.set_preview,
            args=[target_size_getter, fps_mode_getter]
        )
        preview_thread.daemon = True
        preview_thread.start()

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


    # FIXME: thumbnail file clashes when queueing multiple videos at once.

    def set_thumbnail(self):
        subprocess.run([
            'totem-video-thumbnailer',
            self.video_path,
            'thumb.jpg'
        ])
        self.thumbnail.set_from_file('thumb.jpg')

    def set_preview(self, target_size_getter, fps_mode_getter):
        width, height = self.get_resolution()
        fps = self.get_fps()
        duration = self.get_duration()

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

        if not encode_settings:
            return

        _, _, target_pixels, target_fps = encode_settings

        src_pixels = self.height if self.height > self.width else self.width

        # TODO: Remember, change this for RTL.
        subtitle = f'{src_pixels}p@{self.fps} → {target_pixels}p@{target_fps}'

        self.set_subtitle(subtitle)

    def set_state(self, state):
        # If new state and old state are the same:
        if state == self.state:
            return

        is_compressing = state == QueuedVideoState.COMPRESSING
        is_complete = state == QueuedVideoState.COMPLETE

        if is_compressing:
            self.progress_bar.set_fraction(0.0)

        self.progress_bar.set_visible(is_compressing)
        self.status_label.set_visible(is_complete)
        self.action_set_enabled('row.remove', not is_compressing)

        self.state = state

    def set_progress_text(self, label):
        self.progress_bar.set_text(label)

    def get_progress_text(self):
        return self.progress_bar.get_text()

    def pulse_progress(self):
        self.progress_bar.pulse()

    def set_progress_fraction(self, fraction):
        self.progress_bar.set_fraction(fraction)
