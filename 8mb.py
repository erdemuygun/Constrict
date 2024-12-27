#!/usr/bin/python3
import sys
import subprocess
import os
import argparse

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


def transcode(fileInput, fileOutput, bitrate):
    command = [
        'ffmpeg',
            '-y',
            '-hide_banner',
            '-loglevel', 'error',
            '-i', fileInput,
            '-b', str(bitrate) + '',
            '-cpu-used', str(os.cpu_count()),
            '-c:a',
            'copy',
            fileOutput
      ]
    #print(command)
    proc = subprocess.run(
                command,
                capture_output=True,
                # avoid having to explicitly encode
                text=True
    )
    #print(proc.stdout)

""" TODO:
check for non-existent files (or non-video files) -- exit 1 with error msg
allow different units for desired file size
add argument for tolerance level
add arugment for output destination
add more error checking for very low target file sizes
see about audio compression?
"""

argParser = argparse.ArgumentParser("constrict")
argParser.add_argument(
    'file_path',
    help='Location of the video file to be compressed'
)
argParser.add_argument(
    'target_size',
    help='Desired size of the compressed video in MB',
    type=int
)
args = argParser.parse_args()

# Tolerance below 8mb
tolerance = 10
fileInput = args.file_path
fileOutput = fileInput + ".crushed.mp4"
targetSizeMB = args.target_size
targetSizeKB = targetSizeMB * 1024
targetSizeBytes = targetSizeKB * 1024
durationSeconds = get_duration(args.file_path)
bitrate = round( targetSizeBytes / durationSeconds)
beforeSizeBytes = os.stat(fileInput).st_size

if beforeSizeBytes <= targetSizeBytes:
    print("File already meets the target size.")
    sys.exit(1)

factor = 0

attempt = 0
while (factor > 1.0 + (tolerance/100)) or (factor < 1):
    attempt = attempt + 1
    bitrate = round(bitrate * (factor or 1))
    print(f"Attempt {attempt}: Transcoding {fileInput} at bitrate {bitrate}bps")

    transcode(fileInput, fileOutput, bitrate)
    afterSizeBytes = os.stat(fileOutput).st_size
    percentOfTarget = (100/targetSizeBytes)*afterSizeBytes
    factor = 100/percentOfTarget
    print(
        f"Attempt {attempt}:",
        f"Original size: {'{:.2f}'.format(beforeSizeBytes/1024/1024)}MB,",
        f"New size: {'{:.2f}'.format(afterSizeBytes/1024/1024)}MB,",
        f"Percentage of target: {'{:.0f}'.format(percentOfTarget)}%,",
        f"and bitrate {bitrate}bps"
    )
print(f"Completed in {attempt} attempts.")
