
$HOME/pkgs/ffmpeg/bin/ffmpeg -f mpegts -vsync 1 -map 0.0:0.1 -map 0.1 -i /dev/dvb/adapter0/dvr0 -vcodec mpeg4 -vb 428288 -s 320x240 -acodec libmp3lame -ab 96000 -ac 1 -f mpegts -

