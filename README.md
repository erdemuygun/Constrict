# Constrict
### Compress videos to target file sizes

Constrict compresses your videos to your chosen file size — useful for uploading to services with specific file size limits. No more relying on online services for video compression, or the manual trial-and-error of re-encoding at various bitrates yourself.

Features include:

- An intuitive, easy to use interface.
- Automatic calculation of average bitrate (ABR), resolution, framerate, and audio quality each video is re-encoded with to meet the target file size.
- Bulk compression of multiple videos to one output directory.
- Customisation of framerate limits, to ensure a clearer or smoother image.
- A choice of codecs to encode output files with, including H.264, HEVC, AV1, and VP9.

The app attempts to retain as much audiovisual quality as possible for the file size given. However, extremely steep reductions in file size can cause significant loss of quality in the output file, and sometimes compression may not be possible at all. All processing is done locally — and as such, compression speeds are only as fast as your hardware allows.

## Command-line usage
As well as having a GTK-based GUI, Constrict supports running directly from the command line.
```
$ constrict [-h] [-t TOLERANCE] [-o OUTPUT]
                 [--framerate {auto,prefer-clear,prefer-smooth}] [--extra-quality]
                 [--codec {h264,hevc,av1,vp9}]
                 file_path target_size
```

- `file_path` is the location of the original video file to be compressed.
- `target_size` is the desired file size of the compressed video in MB.
- Optional argument `--framerate` adjusts how many frames per second (FPS) will be in the compressed video, if the source framerate is above 30 FPS.
  - `prefer-clear` will limit the framerate to 30 FPS, ensuring higher image clarity due to fewer frames needing detail for a given bitrate. 
  - `prefer-smooth` limits the framerate to 60 FPS, making the video smoother. However, each frame will be less detailed than with `prefer-clear`, because more frames will need to be encoded at the same bitrate --- as a result, the resolution of the compressed video may be further reduced to prevent artifacting and excessive graininess/blurriness.
  - `auto` (default) automatically applies a 30 FPS or 60 FPS limit based on whether or not applying a 60 FPS limit will noticeably impact image clarity.
	
  A 24 FPS limit will be applied to videos at very low bitrates, regardless of the `--framerate` argument passed.
- Optional argument `--codec` takes the video codec to encode the compressed video with. Current options are:
    * H.264 (`h264`)
    * H.265/HEVC (`hevc`)
    * AV1 (`av1`)
    * VP9 (`vp9`)
- Optional argument `--extra-quality` slightly increases image quality at the cost of increased encoding times.
- Optional argument `-t` takes the tolerance of the target file size, a percentage of how much the compressed file size can be under target. A lower tolerance can result in a higher file size closer to target, thus slightly increasing the video quality, but means the script takes longer to run. Default value is 10.
- Optional argument `-o` takes the destination path of the compressed video file. Default value is `[input_file_path].compressed.mp4`.

## Dependencies
- Python
- FFmpeg (full)

## Acknowledgements
Thanks to Matthew Baggett for creating the original ['8mb' repository](https://github.com/matthewbaggett/8mb) which this project used as its foundation.