set PYTHONPATH=..\..;%PYTHONPATH%

python test_merkle_msg.py singtest_good_hashpiece_bepstyle
python test_merkle_msg.py singtest_good_hashpiece_oldstyle
python test_merkle_msg.py singtest_good_request_bepstyle
python test_merkle_msg.py singtest_bad_hashpiece_bepstyle
python test_merkle_msg.py singtest_bad_hashpiece_oldstyle
