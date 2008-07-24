
#FFMPEG=$HOME/pkgs/ffmpeg-r13556/bin/ffmpeg
FFMPEG=$HOME/pkgs/ffmpeg-r14154-x264-r745/bin/ffmpeg
#FFMPEG=$HOME/pkgs/ffmpeg-r14260-x264-snapshot-20080716-2245/bin/ffmpeg

$FFMPEG -f mpegts -vsync 1 -map 0.0:0.1 -map 0.1 -i /dev/dvb/adapter0/dvr0 -vcodec libx264 -vb 428288 -g 16 -s 320x240 -acodec libfaac -ab 96000 -ac 1 -deinterlace -f mpegts -

