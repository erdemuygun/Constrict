# constrict-cli
A command-line tool to easily compress videos to target file sizes. Useful for uploading videos to services with specific file size limits.

See also Constrict (TBA), a GUI wrapper for this script for Linux. You can't see it now though because I haven't started making it yet.

## Usage
```
$ constrict [-t TOLERANCE] [-o OUTPUT] file_path target_size
```

- `file_path` is the location of the original video file to be compressed.
- `target_size` is the desired file size of the compressed video.
- Optional argument `-t` takes the tolerance of the target file size, a percentage of how much the compressed file size can be under target. A lower tolerance can result in a higher file size closer to target, thus slightly increasing the video quality, but means the script takes longer to run. Default value is 10.
- Optional argument `-o` takes the destination path of the compressed video file. Default value is `[input_file_path].compressed.mp4`.

## Acknowledgements
Thanks to Matthew Baggett for creating the original ['8mb' repository](https://github.com/matthewbaggett/8mb) which this project used as its foundation.