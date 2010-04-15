set PYTHONPATH=..\..\..;.

python test_tdef.py
python test_seeding.py test_normal_torrent
python test_seeding.py test_merkle_torrent
python test_tracking.py

