#!/usr/bin/python3
import sys
import subprocess
import os
import argparse
import struct
import shutil

def get_duration(fileInput):
    return float(
        subprocess.check_output([
            "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                fileInput
        ])[:-1]
    )

"""
Returns a suitable resolution preset (i.e. 1080p, 720p, etc.) from a given
bitrate and source resolution. Allows source videos to be shrunk according to
a new, reduced bitrate for optimal perceived video quality. This function should
not return a resolution preset larger than the source resolution (i.e. an
upscaled or stretched resolution).

If -1 is returned, then the video's source resolution is recommended.
"""
def get_res_preset(bitrate, sourceWidth, sourceHeight):
    sourceRes = sourceWidth * sourceHeight # Resolution in terms of pixel count
    bitrateKbps = bitrate / 1000 # Convert to kilobits
    print(f'kbps -- {bitrateKbps}')
    """
    Bitrate-resolution recommendations are taken from:
    https://developers.google.com/media/vp9/settings/vod
    """
    bitrateResMap = {
        12000 : 2160, # 4K
        6000 : 1440, # 2K
        1800 : 1080, # 1080p
        1024 : 720, # 720p
        512 : 480, # 480p
        276 : 360, # 360p
        150 : 240, # 240p
        0 : 144 # 144p
    }

    for bitrateLowerBound, widthPreset in bitrateResMap.items():
        presetRes = widthPreset ** 2 * (16 / 9)
        if bitrateKbps >= bitrateLowerBound and sourceRes >= presetRes:
            return widthPreset

    return -1

def getProgress(fileInput, ffmpegCmd):
    pvCmd = subprocess.Popen(['pv', fileInput], stdout=subprocess.PIPE)
    ffmpegCmd = subprocess.check_output(ffmpegCmd, stdin=pvCmd.stdout)
    pvCmd.wait()

def transcode(
    fileInput,
    fileOutput,
    bitrate,
    sourceWidth,
    sourceHeight,
    keepFramerate
):
    resPresetHeight = get_res_preset(bitrate, sourceWidth, sourceHeight)
    needsDownscaling = resPresetHeight != -1 # -1 means use native resolution

    resPresetWidth = -1
    if needsDownscaling:
        scalingFactor = sourceHeight / resPresetHeight
        resPresetWidthFloat = sourceWidth / scalingFactor
        resPresetWidth = int(((resPresetWidthFloat + 1) // 2) * 2)
                         # Keeps the width divisble by 2 for ffmpeg
        print(f'Video will be shrunk to {resPresetHeight}p.')

    portrait = sourceHeight > sourceWidth
    filterWidth = resPresetHeight if portrait else resPresetWidth
    filterHeight = resPresetWidth if portrait else resPresetHeight

    fpsFilter = '' if keepFramerate else ',fps=30'

    pass1Command = [
        'ffmpeg',
            '-y',
            '-hide_banner',
            '-loglevel', 'error',
            '-i', 'pipe:0',
            '-row-mt', '1',
            #'-deadline', 'realtime',
            '-vf', f'scale={filterWidth}:{filterHeight}{fpsFilter}',
            '-c:v', 'libvpx-vp9',
            '-b:v', str(bitrate) + '',
            '-minrate', str(bitrate * 0.5),
            '-maxrate', str(bitrate * 1.45),
            '-pass', '1',
            '-an',
            '-f', 'null',
            '/dev/null'
    ]
    print(" ".join(pass1Command))
    getProgress(fileInput, pass1Command)

    pass2Command = [
        'ffmpeg',
            '-y',
            '-hide_banner',
            '-loglevel', 'error',
            '-i', 'pipe:0',
            '-row-mt', '1',
            '-cpu-used', '8',
            '-deadline', 'realtime',
            '-vf', f'scale={filterWidth}:{filterHeight}{fpsFilter}',
            '-c:v', 'libvpx-vp9',
            '-b:v', str(bitrate) + '',
            '-minrate', str(bitrate * 0.5),
            '-maxrate', str(bitrate * 1.45),
            '-pass', '2',
            '-c:a', 'libopus',
            fileOutput
    ]

    print(" ".join(pass2Command))
    getProgress(fileInput, pass2Command)

def get_framerate(fileInput):
    command = [
        'ffprobe',
            '-v', '0',
            '-of',
            'default=noprint_wrappers=1:nokey=1',
            '-select_streams', 'v:0',
            '-show_entries',
            'stream=r_frame_rate',
            fileInput
    ]
    fps_bytes = subprocess.check_output(
        command
    )
    fps_fraction = fps_bytes.decode('utf-8')
    fps_fraction_split = fps_fraction.split('/')
    fps_numerator = int(fps_fraction_split[0])
    fps_denominator = int(fps_fraction_split[1])
    fps_float = round(fps_numerator / fps_denominator)
    return(fps_float)

def get_cache_dir():
    homeDir = os.path.expanduser('~')
    cacheDir = os.path.join(homeDir, '.cache/constrict/')
    return cacheDir

def make_cache_dir():
    os.makedirs(get_cache_dir(), exist_ok=True)

def clear_cached_file(filename):
    file = os.path.join(get_cache_dir(), filename)
    os.remove(file)

def apply_30fps(fileInput):
    fileOutput = os.path.join(get_cache_dir(), fileInput)

    command = [
        'ffmpeg',
            '-i', fileInput,
            '-filter:v', 'fps=30',
            '-cpu-used', str(os.cpu_count()),
            '-y',
            fileOutput
    ]

    make_cache_dir()
    print(f'cache file output: {fileOutput}')
    proc = subprocess.run(
        command,
        capture_output=True,
        text=True
    )
    return fileOutput

def get_resolution(fileInput):
    command = [
        'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=s=x:p=0',
            fileInput
    ]

    res_bytes = subprocess.check_output(command)
    res = res_bytes.decode('utf-8')
    res_array = res.split('x')
    width = int(res_array[0])
    height = int(res_array[1])

    return (width, height)

"""
Returns the audio bitrate of input file, once it's re-encoded with Opus codec.
"""
def get_audio_bitrate(fileInput, fileOutput):
    transcodeCommand = [
        'ffmpeg',
            '-y',
            '-i', fileInput,
            '-vn',
            '-c:a', 'libopus',
            fileOutput
    ]

    subprocess.run(transcodeCommand, capture_output=True, text=True)

    probeCommand = [
        'ffprobe',
            '-v', 'error',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=bit_rate',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            fileOutput
    ]

    try:
        bitrateStr = subprocess.check_output(probeCommand)
        return int(bitrateStr)
    except ValueError:
        print('Could not get valid bitrate.')
        return None

""" TODO:
check for non-existent files (or non-video files) -- exit 1 with error msg
allow different units for desired file size
add input validation for arguments
add overwrite confirmation and argument
change output file format
check for when file size doesnt change
add more error checking for very low target file sizes
see about audio compression / changing sample rate?
add support for bulk compression
support more video formats
add different preset resolutions for 60fps
perhaps add a fast/slow option?
add 'keep resolution' argument?
"""

argParser = argparse.ArgumentParser("constrict")
argParser.add_argument(
    'file_path',
    help='Location of the video file to be compressed',
    type=str
)
argParser.add_argument(
    'target_size',
    help='Desired size of the compressed video in MB',
    type=int
)
argParser.add_argument(
    '-t',
    dest='tolerance',
    type=int,
    help='Tolerance of end file size under target in percent (default 10)'
)
argParser.add_argument(
    '-o',
    dest='output',
    type=str,
    help='Destination path of the compressed video file'
)
argParser.add_argument(
    '--keep-framerate',
    action='store_true',
    help='Keep the source framerate; do not lower to 30FPS'
)
args = argParser.parse_args()

# Tolerance below 8mb
tolerance = args.tolerance or 10
#print(f'Tolerance: {tolerance}')
fileInput = args.file_path
fileOutput = args.output or (fileInput + ".crushed.mp4")
targetSizeMB = args.target_size
targetSizeKB = targetSizeMB * 1024
targetSizeBytes = targetSizeKB * 1024
targetSizeBits = targetSizeBytes * 8
durationSeconds = get_duration(args.file_path)

targetVideoBitrate = round(targetSizeBits / durationSeconds)
print(f'Target total bitrate: {targetVideoBitrate}bps')
audioBitrate = get_audio_bitrate(fileInput, fileOutput)

if audioBitrate is None:
    print('No audio bitrate found')
else:
    print(f'Audio bitrate: {audioBitrate}bps')
    if (targetVideoBitrate - audioBitrate >= 1000):
        targetVideoBitrate -= audioBitrate
        print('Subtracting audio bitrate from target video bitrate')

targetVideoBitrate *= 0.99
# To account for metadata and such... shouldn't try to use a bitrate EXACTLY on
# target as it'll likely overshoot, and another attempt will have to be made.

# if targetSizeMB < 25:
    #targetVideoBitrate *= 0.95
#     print('Bitrate lowered by 5%')
    # Slightly lower bitrate target to account for file metadata and such.
# elif targetSizeMB > 75:
#     targetVideoBitrate *= 1.05
#     print('Bitrate increased by 5%')

beforeSizeBytes = os.stat(fileInput).st_size

if beforeSizeBytes <= targetSizeBytes:
    sys.exit("File already meets the target size.")

framerate = get_framerate(fileInput)
print(f'framerate: {framerate}')
keepFramerate = framerate <= 30 or args.keep_framerate
print(f'keep framerate: {keepFramerate}')

width, height = get_resolution(fileInput)
print(f'Resolution: {width}x{height}')
pixels = width * height
print(f'Total pixels: {pixels}')

cacheOccupied = False

factor = 0
attempt = 0
while (factor > 1.0 + (tolerance / 100)) or (factor < 1):
    attempt = attempt + 1
    targetVideoBitrate = round((targetVideoBitrate) * (factor or 1))

    if (targetVideoBitrate < 1000):
        if cacheOccupied:
            clear_cached_file(reducedFpsFile)
        sys.exit(f"Bitrate got too low ({targetVideoBitrate}bps); aborting")

    print(f"Attempt {attempt} -- transcoding {fileInput} at bitrate {targetVideoBitrate}bps")

    transcode(
        fileInput,
        fileOutput,
        targetVideoBitrate,
        width,
        height,
        keepFramerate
    )
    afterSizeBytes = os.stat(fileOutput).st_size
    percentOfTarget = (100 / targetSizeBytes) * afterSizeBytes

    factor = 100 / percentOfTarget

    if (percentOfTarget > 100):
        # Prevent a lot of attempts resulting in above-target sizes
        factor -= 0.1
        print(f'Reducing factor by 10%')

    print(
        f"Attempt {attempt} --",
        f"original size: {'{:.2f}'.format(beforeSizeBytes/1024/1024)}MB,",
        f"new size: {'{:.2f}'.format(afterSizeBytes/1024/1024)}MB,",
        f"percentage of target: {'{:.0f}'.format(percentOfTarget)}%,",
        f"bitrate: {targetVideoBitrate}bps"
    )
if cacheOccupied:
    clear_cached_file(reducedFpsFile)
print(f"Completed in {attempt} attempts.")
