#!/usr/bin/python3
import sys
import subprocess
import os
import argparse
import datetime


def get_duration(file_input):
    return float(
        subprocess.check_output([
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_input
        ])[:-1]
    )


def new_file(file_path):
    """
    Returns a unique file path for the file path given. Ensures that no file is
    overwritten, as if the input file path already exists, the file path output
    will be in the form of '{file_root}-{n}{file_ext}' where n incremented with
    every existing file in the directory.

    Do not use if you *want* to overwrite something.
    """

    final_path = file_path
    root_ext = os.path.splitext(file_path)

    counter = 0
    while os.path.exists(final_path):
        counter += 1
        final_path = f'{root_ext[0]}-{counter}{root_ext[1]}'

    return final_path


def get_res_preset(bitrate, source_width, source_height, framerate):
    """
    Returns a suitable resolution preset (i.e. 1080p, 720p, etc.) from a given
    bitrate and source resolution. Allows source videos to be shrunk according
    to a new, reduced bitrate for optimal perceived video quality. This
    function should not return a resolution preset larger than the source
    resolution (i.e. an upscaled or stretched resolution).

    -If -1 is returned, then the video's source resolution is recommended.
    """

    source_pixels = source_width * source_height  # Get pixel count
    bitrate_Kbps = bitrate / 1000  # Convert to kilobits
    """
    Bitrate-resolution recommendations are taken from:
    https://developers.google.com/media/vp9/settings/vod
    """
    bitrate_res_map_30 = {
        12000: (3840, 2160),  # 4K
        6000: (2560, 1440),  # 2K
        1800: (1920, 1080),  # 1080p
        1024: (1280, 720),  # 720p
        512: (640, 480),  # 480p
        276: (640, 360),  # 360p
        150: (320, 240),  # 240p
        0: (192, 144)  # 144p
    }
    bitrate_res_map_60 = {
        18000: (3840, 2160),  # 4K
        9000: (2560, 1440),  # 2K
        3000: (1920, 1080),  # 1080p
        1800: (1280, 720),  # 720p
        750: (640, 480),  # 480p
        276: (640, 360),  # 360p
        150: (320, 240),  # 240p
        0: (192, 144)  # 144p
    }

    bitrate_res_map = (
        bitrate_res_map_30 if framerate <= 30 else bitrate_res_map_60
    )

    # print(bitrate_res_map)

    for bitrate_lower_bound, res_preset in bitrate_res_map.items():
        preset_width, preset_height = res_preset[0], res_preset[1]
        preset_pixels = preset_width * preset_height
        if (
            bitrate_Kbps >= bitrate_lower_bound and
            source_pixels >= preset_pixels
        ):
            return preset_height

    return -1


def get_encoding_speed(frame_height):
    return 'medium' if frame_height > 480 else 'slower'  # H.264 version
    # return '2' if frame_height > 480 else '1'  # VP9 version


def get_progress(file_input, ffmpeg_cmd):
    pv_cmd = subprocess.Popen(['pv', file_input], stdout=subprocess.PIPE)
    ffmpeg_cmd = subprocess.check_output(ffmpeg_cmd, stdin=pv_cmd.stdout)
    pv_cmd.wait()


def transcode(
    file_input,
    file_output,
    bitrate,
    width,
    height,
    framerate,
    extra_quality,
    crush_audio
):
    portrait = height > width
    frame_height = width if portrait else height

    print(f' frame height: {frame_height}')

    preset = get_encoding_speed(frame_height)
    fps_filter = '' if framerate == -1 else f',fps={framerate}'

    pass1_cmd = [
        'ffmpeg',
        '-y',
        '-hide_banner',
        '-loglevel', 'error',
        '-i', 'pipe:0',
        '-row-mt', '1',
        '-frame-parallel', '1',
        '-preset', f'{preset}',
        # '-deadline', 'good',
        # '-cpu-used', '4',
        # '-threads', '24',
        '-vf', f'scale={width}:{height}{fps_filter}',
        '-c:v', 'libx264',
        '-b:v', str(bitrate) + '',
        '-pass', '1',
        '-an',
        '-f', 'null',
        '/dev/null'
    ]
    print(" ".join(pass1_cmd))
    print(' Transcoding... (pass 1/2)')
    get_progress(file_input, pass1_cmd)

    # cpu_used = get_encoding_speed(frame_height) if extra_quality else '4'

    pass2_cmd = [
        'ffmpeg',
        '-y',
        '-hide_banner',
        '-loglevel', 'error',
        '-i', 'pipe:0',
        '-row-mt', '1',
        '-frame-parallel', '1',
        '-preset', f'{preset}',
        # '-threads', '24',
        # '-deadline', 'good',
        # '-cpu-used', cpuUsed,
        '-vf', f'scale={width}:{height}{fps_filter}',
        '-c:v', 'libx264',
        '-b:v', str(bitrate) + '',
        '-pass', '2',
        # '-x265-params', 'pass=1',
        '-c:a', 'libopus'
        # '-b:a', '6k',
        # '-ac', '1',
    ]
    if crush_audio:
        pass2_cmd.extend(['-b:a', '6k', '-ac', '1'])
    pass2_cmd.append(file_output)
    print(" ".join(pass2_cmd))
    print(' Transcoding... (pass 2/2)')
    get_progress(file_input, pass2_cmd)


def get_framerate(file_input):
    cmd = [
        'ffprobe',
        '-v', '0',
        '-of',
        'default=noprint_wrappers=1:nokey=1',
        '-select_streams', 'v:0',
        '-show_entries',
        'stream=r_frame_rate',
        file_input
    ]
    fps_bytes = subprocess.check_output(cmd)
    fps_fraction = fps_bytes.decode('utf-8')
    fps_fraction_split = fps_fraction.split('/')
    fps_numerator = int(fps_fraction_split[0])
    fps_denominator = int(fps_fraction_split[1])
    fps_float = round(fps_numerator / fps_denominator)
    return fps_float


def is_streamable(file_input):
    cmd = ['head', file_input]
    file_head = subprocess.check_output(cmd)

    moov_bytes = 'moov'.encode('utf-8')
    mdat_bytes = 'mdat'.encode('utf-8')

    #  print(f'moov found: {moov_bytes in file_head}')
    #  print(f'mdat found: {mdat_bytes in file_head}')

    if moov_bytes not in file_head:
        return mdat_bytes not in file_head

    # moov is now confirmed to be present

    if mdat_bytes not in file_head:
        return True

    # mdia is now confirmed to be present

    moov_index = file_head.index(moov_bytes)
    mdat_index = file_head.index(mdat_bytes)

    # print(moov_index)
    # print(mdat_index)

    # faststart enabled if 'moov' shows up before 'mdia'
    return moov_index < mdat_index


def make_streamable(file_input, file_output):
    cmd = ['qt-faststart', file_input, file_output]
    subprocess.run(cmd, stdout=subprocess.DEVNULL)


def get_resolution(file_input):
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'csv=s=x:p=0',
        file_input
    ]

    res_bytes = subprocess.check_output(cmd)
    res = res_bytes.decode('utf-8')
    res_array = res.split('x')
    width = int(res_array[0])
    height = int(res_array[1])

    return (width, height)


def get_audio_bitrate(file_input, file_output):
    """
    Returns the audio bitrate of input file, once it's re-encoded with Opus
    codec.
    """
    transcode_cmd = [
        'ffmpeg',
        '-y',
        '-v', 'error',
        '-i', 'pipe:0',
        '-vn',
        '-c:a', 'libopus',
        #  '-b:a', '12k',
        file_output
    ]

    display_heading('Getting audio bitrate...')
    get_progress(file_input, transcode_cmd)
    #  subprocess.run(transcode_cmd, capture_output=True, text=True)

    probe_cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'a:0',
        '-show_entries', 'stream=bit_rate',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        file_output
    ]

    try:
        bitrate_str = subprocess.check_output(probe_cmd)
        return int(bitrate_str)
    except ValueError:
        print(' Could not get valid bitrate.')
        return 0


def bold(text):
    return f'\033[1m{text}\033[0m'


def display_heading(text):
    print(f':: {bold(text)}')


def print_table(data):
    max_key_len = 0
    max_value_len = 0

    for row in data:
        row[0] += ':'

        if len(row[0]) > max_key_len:
            max_key_len

        max_key_len = (
            len(row[0]) if len(row[0]) > max_key_len else max_key_len
        )
        max_value_len = (
            len(row[1]) if len(row[1]) > max_value_len else max_value_len
        )

    for row in data:
        spaces_to_add = max_key_len - len(row[0])
        for i in range(spaces_to_add):
            row[0] += ' '

        spaces_to_add = max_value_len - len(row[1])
        for i in range(spaces_to_add):
            row[1] = ' ' + row[1]

        print(f' {row[0]}  {row[1]}')


""" TODO:
check for non-existent files (or non-video files) -- exit 1 with error msg
allow different units for desired file size
add input validation for arguments
add overwrite confirmation and argument
add 'source overwrite' mode: -o value same as input file path
change output file format
check for when file size doesnt change
add more error checking for very low target file sizes
see about audio compression / changing sample rate?
add support for bulk compression
support more video formats
perhaps add a fast/slow option?
add 'keep resolution' argument?
add 'general compression' mode - no target file size
reconsider where log and streamable files go (output dir rather than PWD?)
add verbosity options (GUI and quiet)
don't use streamable temp file with quiet verbosity mode
add overwrite-safe default file outputs (streamable file and compressed file)
Add check when video bitrate calculation goes over original bitrate
change how tolerance works
change res preset function to use full width*height resolutions
add AV1 option parameter
inhibit suspend while running
get rid of all this unused and commented out code
investigate error messages and performance further
use some kind of maths magic to reduce number of attempts at low file sizes
improve bitrate recalculation, change from simple multiplication (!!)
further reduce framerate at 144p
add ffmpeg tune options maybe?
readjust audio bitrate calculation (no scanning)
check calculations for bitrate etc. are correct (i.e. MiB vs MB etc)
add checkers for codecs
clean up ffmpeg 2pass logs after compression
change 'keep-framerate' to 'prefer-smoothness' and lock to 60 FPS
"""

arg_parser = argparse.ArgumentParser("constrict")
arg_parser.add_argument(
    'file_path',
    help='Location of the video file to be compressed',
    type=str
)
arg_parser.add_argument(
    'target_size',
    help='Desired size of the compressed video in MB',
    type=int
)
arg_parser.add_argument(
    '-t',
    dest='tolerance',
    type=int,
    help='Tolerance of end file size under target in percent (default 10)'
)
arg_parser.add_argument(
    '-o',
    dest='output',
    type=str,
    help='Destination path of the compressed video file'
)
arg_parser.add_argument(
    '--keep-framerate',
    action='store_true',
    help='Keep the source framerate; do not lower to 30FPS'
)
arg_parser.add_argument(
    '--extra-quality',
    action='store_true',
    help='Increase image quality at the cost of longer encoding times'
)
args = arg_parser.parse_args()

start_time = datetime.datetime.now().replace(microsecond=0)

# Tolerance below 8mb
tolerance = args.tolerance or 10
# print(f'Tolerance: {tolerance}')
file_input = args.file_path
file_output = args.output

if file_output is None:  # i.e., if -o hasn't been passed
    root_ext = os.path.splitext(file_input)
    file_output = new_file(f'{root_ext[0]} (compressed).mp4')

target_size_MiB = args.target_size
target_size_KiB = target_size_MiB * 1024
target_size_bytes = target_size_KiB * 1024
target_size_bits = target_size_bytes * 8
duration_seconds = get_duration(file_input)
extra_quality = args.extra_quality

is_input_streamable = is_streamable(file_input)
streamable_input = 'streamable_input'

if not is_input_streamable:
    display_heading('Creating input stream...')

    root_ext = os.path.splitext(file_input)
    streamable_input = new_file(f'{root_ext[0]}-stream{root_ext[1]}')

    make_streamable(file_input, streamable_input)
    file_input = streamable_input

# print(f'Fast start enabled: {is_input_streamable}')

before_size_bytes = os.stat(file_input).st_size

if before_size_bytes <= target_size_bytes:
    sys.exit("File already meets the target size.")

reduction_factor = target_size_bytes / before_size_bytes

# A method to try to reduce number of attempts taken to compress a file.
# These hardcoded values are based on a 185MiB video I compressed to various
# target sizes, seeing where the compression would start to go over the target
# size or under the target size with 10% tolerance. Anyone with a more
# sophisticated solution to this is welcome to submit a pull request.

# TODO: revisit this (esp. with extra quality mode and keep framerate)

# shrunkSize = target_size_bits
# if reduction_factor < (18 / 185):
#     print('reducing target by 10%')
#     shrunkSize *= 0.9
# elif reduction_factor > (160 / 185):
#     print('increasing by 30%')
#     target_size_MiB *= 1.3
# elif reduction_factor > (85 / 185):
#     print('increasing target by 30%')
#     shrunkSize *= 1.3
# elif reduction_factor > (52 / 185):
#     print('increasing target by 20%')
#     shrunkSize *= 1.2
# elif reduction_factor > (30 / 185):
#     print('increasing target by 10%')
#     shrunkSize *= 1.1

target_total_bitrate = round(target_size_bits / duration_seconds)
target_video_bitrate = target_total_bitrate
audio_bitrate = None

crush_mode = False

if (target_total_bitrate / 1000) < 150:  # If target bitrate less than 150Kbps:
    audio_bitrate = 6000
    crush_mode = True
else:
    audio_bitrate = get_audio_bitrate(file_input, file_output)

# print(f'Target total bitrate: {target_total_bitrate}bps')

if audio_bitrate is None:
    print('\n No audio bitrate found')
else:
    print(f'\n Audio bitrate: {audio_bitrate // 1000}Kbps')
    if (target_video_bitrate - audio_bitrate >= 1000):
        target_video_bitrate -= audio_bitrate
        #  print('Subtracting audio bitrate from target video bitrate')

if crush_mode:
    print('Target should be adjusted here...')

target_video_bitrate *= 0.99
# To account for metadata and such... shouldn't try to use a bitrate EXACTLY on
# target as it'll likely overshoot, and another attempt will have to be made.

# if targetSizeMB < 25:
#   target_video_bitrate *= 0.95
#     print('Bitrate lowered by 5%')
# Slightly lower bitrate target to account for file metadata and such.
# elif targetSizeMB > 75:
#     target_video_bitrate *= 1.05
#     print('Bitrate increased by 5%')

source_fps = get_framerate(file_input)
width, height = get_resolution(file_input)
# print(f'Resolution: {width}x{height}')
pixels = width * height
# print(f'Total pixels: {pixels}')
portrait = width < height

factor = 0
attempt = 0
while (factor > 1.0 + (tolerance / 100)) or (factor < 1):
    attempt = attempt + 1
    target_video_bitrate = round((target_video_bitrate) * (factor or 1))

    if (target_video_bitrate < 1000):
        sys.exit("Bitrate got too low (<1000bps); aborting")

    target_height = height
    target_width = width

    if (target_video_bitrate / 1000) <= 150:  # If vid bitrate 150Kbps or less
        crush_mode = True

    compressed_fps = 24 if crush_mode else 30
    keep_fps = source_fps <= compressed_fps or args.keep_framerate
    target_fps = source_fps if keep_fps else compressed_fps

    if True:  # if (!keep resolution), later on
        preset_height = get_res_preset(
            target_video_bitrate,
            width,
            height,
            target_fps
        )

        print(f'Target height {preset_height}')

        if preset_height != -1:  # If being downscaled:
            target_height = preset_height
            scaling_factor = height / target_height
            target_width = int(((width / scaling_factor + 1) // 2) * 2)

            if portrait:
                # Swap height and width
                buffer = target_width
                target_width = target_height
                target_height = buffer

    displayed_res = target_width if portrait else target_height

    print()
    display_heading((
        f'(Attempt {attempt}) '
        f'compressing to {target_video_bitrate // 1000}Kbps / '
        f'{displayed_res}p@{target_fps}...'
    ))

    transcode(
        file_input,
        file_output,
        target_video_bitrate,
        target_width,
        target_height,
        -1 if keep_fps else target_fps,
        extra_quality,
        crush_mode
    )
    after_size_bytes = os.stat(file_output).st_size
    percent_of_target = (100 / target_size_bytes) * after_size_bytes

    factor = 100 / percent_of_target

    if (percent_of_target > 100):
        # Prevent a lot of attempts resulting in above-target sizes
        factor -= 0.05
        #  print(f'Reducing factor by 5%')

    print()
    print_table([
        ['New Size', f"{'{:.2f}'.format(after_size_bytes/1024/1024)}MB"],
        ['Percentage of Target', f"{'{:.0f}'.format(percent_of_target)}%"]
    ])

if not is_input_streamable:
    os.remove(streamable_input)

time_taken = datetime.datetime.now().replace(microsecond=0) - start_time
print(f"\nCompleted in {time_taken}.")


