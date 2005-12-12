# Generated from bt_MakeCreateIcons - 05/10/04 22:15:33
# T-0.3.0 (BitTornado)

from binascii import a2b_base64
from zlib import decompress
from os.path import join

icons = {
    "icon_bt.ico":
        "eJyt1K+OFEEQx/FaQTh5GDRZhSQpiUHwCrxCBYXFrjyJLXeXEARPsZqUPMm+" +
        "AlmP+PGtngoLDji69zMz2zt/qqtr1mxHv7621d4+MnvK/jl66Bl2drV+e7Wz" +
        "S/v12A7rY4fDtuvOwfF4tOPXo52/fLLz+WwpWd6nqRXHKXux39sTrtnjNd7g" +
        "PW7wGSd860f880kffjvJ2QYS1Zcw4AjcoaA5yRFIFDQXOgKJguZmjkCioB4T" +
        "Y2CqxpTXA7sHEgVNEC8RSBQ0gfk7xtknCupgk3EEEgXlNgFHIFHQTMoRSBQ0" +
        "E+1ouicKmsk7AomCJiGOQKKgSZIjkChoEucIJAqaZDoCiYImwb4iydULmqQ7" +
        "AomC1kLcEQ/jSBQ0i+MIJAqaBXMEElVdi9siOgKJgmZhfWWlVjTddXW/FtsR" +
        "SBQ0BeAIJAqaonAEEgVNoTgCiYKmeByBREHaqiVWRtSRrAJzBBIFTdE5AomC" +
        "phBPpxPP57dVkDfrTl063nUVnWe383fZx9tb3uN+o7U+BLDtuvcQm8d/27Y/" +
        "jO3o5/ay+YPv/+f6y30e1OyB7QcsGWFj",
    "icon_done.ico":
        "eJyt1K2OVEEQhuEaQbJyMWgyCklSEoPgFvYWKigsduRKbLndhCC4itGk5Erm" +
        "Fsh4xMdbfSoMOGDpnuf89Jyf6uqaMdvRr69ttbdPzJ6xf4Eeeo6dXa3vXu/s" +
        "0n49tsP62OGw7bpzcDwe7fj1aOcvn+x8PltKlg9pasVxyl7u9/aUe/Z4gxu8" +
        "xy0+44Rv/Yp/vujDbxc520Ci+hYGHIF7FDQXOQKJguZGRyBR0DzMEUgU1GNi" +
        "DEzVmPJ6YfdAoqAJ4hUCiYImMH/HOPtEQR1sMo5AoqDcJuAIJAqaSTkCiYJm" +
        "oh1N90RBM3lHIFHQJMQRSBQ0SXIEEgVN4hyBREGTTEcgUdAk2FckuXpBk3RH" +
        "IFHQWoh74mEciYJmcRyBREGzYI5AoqprcVtERyBR0Cysr6zUiqa7rh7WYjsC" +
        "iYKmAByBREFTFI5AoqApFEcgUdAUjyOQKEhbtcTKiDqSVWCOQKKgKTpHIFHQ" +
        "FOLpdOL9fLcK8nY9qUvHu66i8+x2/i77eHfH77h/0VofAth23Xuoz/+2bX8Y" +
        "29HP7WXzB+f/5/7Lcx7V7JHtB9dPG3I=",
    "black.ico":
        "eJzt1zsOgkAYReFLLCztjJ2UlpLY485kOS7DpbgESwqTcQZDghjxZwAfyfl0" +
        "LIieGzUWSom/pan840rHnbSUtPHHX9Je9+tAh2ybNe8TZZ/vk8ajJ4zl6JVJ" +
        "+xFx+0R03Djx1/2B8bcT9L/bt0+4Wq+4se8e/VTfMvGqb4n3nYiIGz+lvt9s" +
        "9EpE2T4xJN4xNFYWU6t+JWXuXDFzTom7SodSyi/S+iwtwjlJ80KaNY/C34rW" +
        "aT8nvK5uhF7ohn7Yqfb87kffLAAAAAAAAAAAAAAAAAAAGMUNy7dADg==",
    "blue.ico":
        "eJzt10EOwUAYhuGv6cLSTux06QD2dTM9jmM4iiNYdiEZ81cIFTWddtDkfbQW" +
        "De8XogtS5h9FIf+81H4jLSSt/ekvaavrdaCDez4SZV+PpPHoicBy9ErSfkQ8" +
        "fCI6Hjgx6f7A+McJ+r/t95i46xMP7bf8Uz9o4k0/XMT338voP5shK0MkjXcM" +
        "YSqam6Qunatyf7Nk7iztaqk8SaujNLfzIM0qKX88ZX8rWmf7Nfa+W8N61rW+" +
        "7TR7fverHxYAAAAAAAAAAAAAAAAAAIziApVZ444=",
    "green.ico":
        "eJzt1zEOgjAAheFHGBzdjJuMHsAdbybxNB7Do3gERwaT2mJIBCOWlqok/yc4" +
        "EP1fNDIoZfZRFLLPa5120krS1p72kvZ6XAeGHLtHouzrkTQePOFZDl5J2g+I" +
        "+08Exz0nZt2PjH+coP/bvveEaY2L+/VN13/1PSbe9v0FfP+jTP6ziVmJkTQ+" +
        "MISZaO6SujSmyu3dkpmbdKil8iptLtLSnWdpUUn58yn3t6J39l/j3tc2XM91" +
        "Xd/tNHt296sfFgAAAAAAAAAAAAAAAAAATOIOVLEoDg==",
    "red.ico":
        "eJzt10EOwUAYhuGv6cLSTux06QD2dTOO4xiO4giWXUjG/BVCRTuddtDkfbQW" +
        "De8XogtS5h9FIf+81GEjLSSt/ekvaavbdaCVez0SZd+PpPHoicBy9ErSfkQ8" +
        "fCI6Hjgx6f7AeOcE/d/2QyceesaD+g1/1u+e+NwPF/H99zL6z2bIyhBJ4y1D" +
        "mIb6LqlK5/a5v1syd5F2lVSepdVJmtt5lGZ7KX8+ZX8rGmfzNfa+e8N61rW+" +
        "7dR7fverHxYAAAAAAAAAAAAAAAAAAIziCpgs444=",
    "white.ico":
        "eJzt1zsOgkAYReFLKCztjJ2ULsAed6bLcRnuwYTaJVhSmIwzGBLEiD8D+EjO" +
        "p2NB9NyosVBK/C3L5B+XOmykhaS1P/6StrpfBzoUp6J5nyj7fJ80Hj1hLEev" +
        "TNqPiNsnouPGib/uD4y/naD/3b59wtV6xY199+in+paJV31LvO9ERNz4KfX9" +
        "ZqNXIsr2iSHxjqGxspha9Sspc+f2qXNK3FXalVJ+kVZnaR7OUZrtpbR5FP5W" +
        "tE77OeF1dSP0Qjf0w06153c/+mYBAAAAAAAAAAAAAAAAAMAobj//I7s=",
    "yellow.ico":
        "eJzt1zsOgkAYReFLKCztjJ2ULsAedybLcRkuxSVYUpiM82M0ihGHgVFJzidY" +
        "ED03vgqlzN+KQv5+qf1GWkha+9Nf0lbX60AX556ORNnXI2k8eiKwHL2StB8R" +
        "D5+IjgdOTLo/MP5xgv5v+8ETd/3iYf2W/+oHTLzth4t4/3sZ/WszZGWIpPGO" +
        "IUxE8yupS+eq3H9smTtLu1oqT9LqKM3tPEizSsofT9nfitbZfow979awnnWt" +
        "bzvNnt/96osFAAAAAAAAAAAAAAAAAACjuABhjmIs",
    "black1.ico":
        "eJzt0zEOgkAUANEhFpZSGTstTWzkVt5Cj8ZROAIHMNGPWBCFDYgxMZkHn2Iz" +
        "G5YCyOLKc+K54XSANbCPiSV2tOt/qjgW3XtSnN41FH/Qv29Jx/P7qefp7W8P" +
        "4z85HQ+9JRG/7BpTft31DPUKyiVcFjEZzQ/TTtdzrWnKmCr6evv780qSJEmS" +
        "JEmSJEmSJEmSpPnunVFDcA==",
    "green1.ico":
        "eJzt0zEKwkAQRuEXLCyTSuy0DHgxb6F4shzFI+QAgpkkFoombowIwvt2Z4vh" +
        "X5gtFrJYRUGca/Y7WAFlVLTY0vf/1elxTwqP3xoKf5B/vjIenp+fOs+r/LWT" +
        "/uQ34aGpUqQnv+1ygDqHagnHRVRG+2H6unfrtZkq6hz5evP7eSVJkiRJkiRJ" +
        "kiRJkiRJ0nwNoWQ+AA==",
    "yellow1.ico":
        "eJzt0zEKwkAQRuEXLCxNJXZaCl7MW8Sj5SgeIQcQ4oS1UDTJxkhAeN/ubDH8" +
        "C7PFQhGrLIlzx/kEW+AYFS0OpP6/atuXPSk8fKsv/EX+/cpweH5+6jyf8kn+" +
        "k0fCfVPlyE/+2q2CZgP1Gi6rqILuw6R69uh1mTrqGvlmv/y8kiRJkiRJkiRJ" +
        "kiRJkiRpvjsp9L8k",
    "alloc.gif":
        "eJxz93SzsEw0YRBh+M4ABi0MS3ue///P8H8UjIIRBhR/sjAyMDAx6IAyAihP" +
        "MHAcYWDlkPHYsOBgM4ewVsyJDQsPNzEoebF8CHjo0smjH3dmRsDjI33C7Dw3" +
        "MiYuOtjNyDShRSNwyemJguJJKhaGS32nGka61Vg2NJyYKRd+bY+nwtMzjbqV" +
        "Qh84gxMCJgnlL4vJuqJyaa5NfFLNLsNVV2a7syacfVWkHd4bv7RN1ltM7ejm" +
        "tMtNZ19Oyb02p8C3aqr3dr2GbXl/7fZyOej5rW653WZ7MzzHZV+v7O2/EZM+" +
        "Pt45kbX6ScWHNWfOilo3n5thucXv8org1XF3DRQYrAEWiVY3"
}

def GetIcons():
    return icons.keys()

def CreateIcon(icon, savedir):
    try:
        f = open(join(savedir,icon),"wb")
        f.write(decompress(a2b_base64(icons[icon])))
        success = 1
    except:
        success = 0
    try:
        f.close()
    except:
        pass
    return success
