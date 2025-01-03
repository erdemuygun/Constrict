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
    https://support.video.ibm.com/hc/en-us/articles/207852117-Internet-connection-and-recommended-encoding-settings
    """
    bitrateResMap = {
        14000 : -1, # Native
        8000 : 2160, # 4K
        4000 : 1080, # 1080p
        1500 : 720, # 720p
        1200 : 480, # 480p
        800 : 360, # 360p
        400 : 270, # 270p
        0 : 144 # 144p
    }

    for bitrateLowerBound, widthPreset in bitrateResMap.items():
        presetRes = widthPreset ** 2 * (16 / 9)
        if bitrateKbps >= bitrateLowerBound and sourceRes >= presetRes:
            return widthPreset

    return -1

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

    command = [
        'ffmpeg',
            '-y',
            '-hide_banner',
            '-loglevel', 'error',
            '-i', fileInput,
            '-b:v', str(bitrate) + '',
            '-b:a', str(bitrate) + '',
            '-cpu-used', str(os.cpu_count()),
            '-vf', f'scale={filterWidth}:{filterHeight}{fpsFilter}',
            '-c:a',
            'copy',
            fileOutput
    ]
    proc = subprocess.run(
        command,
        capture_output=True,
        # avoid having to explicitly encode
        text=True
    )
    #print(proc.stdout)

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

def get_audio_bitrate(fileInput):
    command = [
        'ffprobe',
            '-v', 'error',
            '-select_streams', 'a:0',
            '-show_entries', 'stream=bit_rate',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            fileInput
    ]

    try:
        bitrateStr = subprocess.check_output(command)
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
change framerate to 30fps by default
see about audio compression / changing sample rate?
add HEVC support
add support for bulk compression
support more video formats
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
audioBitrate = get_audio_bitrate(fileInput)

if audioBitrate is None:
    print('No audio bitrate found')
else:
    print(f'Audio bitrate: {audioBitrate}bps')
    targetVideoBitrate -= audioBitrate

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
        if (attempt == 1 and audioBitrate is None):
            audioBitrate = get_audio_bitrate(fileOutput)
            # Output file may have audio bitrate info that input file didn't
            # have (e.g. MKV -> MP4 conversion), so try getting and using this
            # once.
            print(f'Output audio bitrate: {audioBitrate}')
            if (audioBitrate is not None):
                targetVideoBitrate -= audioBitrate
                factor = 0
            else:
                if factor > 0.1:
                    factor -= 0.1
                    print(f'Reducing factor by 10%')
        else:
            if factor > 0.1:
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
