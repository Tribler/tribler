
set PYTHONPATH=..\..

python test_subtitles_isolation.py
python test_channelcast_plus_subtitles.py singtest_plain_nickname
python test_channelcast_plus_subtitles.py singtest_unicode_nickname
python test_subtitles_msgs.py singtest_subs_messages

