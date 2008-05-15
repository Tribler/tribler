
ffmpeg -s 320x240 -r 15 -f video4linux -i /dev/video -vcodec mpeg4 -vb 428288 -s 320x240 -an -f mpegts -
