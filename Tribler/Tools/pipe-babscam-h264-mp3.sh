
$HOME/pkgs/ffmpeg-r13556/bin/ffmpeg -f mpegts -i /dev/dvb/adapter0/dvr0 -vcodec libx264 -vb 428288 -s 320x240 -acodec libmp3lame -ab 96000 -ac 1 -deinterlace -f mpegts -

