
# X264ENCOPTS='bitrate=1024'
# X264ENCOPTS='vbv-maxrate=1024:vbv-minrate=1024:qcomp=0:ratetol=0:keyint=30:frameref=1'
X264ENCOPTS='bitrate=1024:qcomp=0:ratetol=0:keyint=30:frameref=1:level=4.1'

mencoder -cache 8192 -ovc x264 -x264encopts "$X264ENCOPTS" -nosound  -of lavf -lavfopts i_certify_that_my_video_stream_does_not_use_b_frames:format=mpegts -vf scale=640:360 -quiet -o /dev/stdout /dev/dvb/adapter0/dvr0 

