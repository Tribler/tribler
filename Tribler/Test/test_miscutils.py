
from Tribler.Core.APIImplementation.miscutils import parse_playtime_to_secs

assert parse_playtime_to_secs("0") == 0.0
assert parse_playtime_to_secs("0.1") == 0.1
assert parse_playtime_to_secs("1:00") == 60.0
assert parse_playtime_to_secs("1:0.3") == 60.3
assert parse_playtime_to_secs("10:00") == 600.0
assert parse_playtime_to_secs("10:56:11") == 39371.00
assert parse_playtime_to_secs("10:56:11.77") == 39371.77
