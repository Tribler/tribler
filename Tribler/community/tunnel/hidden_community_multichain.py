from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity


class HiddenTunnelCommunityMultichain(HiddenTunnelCommunity):

    @classmethod
    def get_master_members(cls, dispersy):
        # generated: Thu May 26 17:04:23 2016
        # curve: None
        # len: 571 bits ~ 144 bytes signature
        # pub: 170 3081a7301006072a8648ce3d020106052b81040027038192000404363b98b8145f66d0b74136fdb1d3699
        #          bdb62d394417f10b3be31d94ac3779261e26b9dde1416362a021dbdfbc5616e88b8bd0fb6e924e893a199
        #          2f53498c4086b96fae02f9e78c00064b92ceea9c97cbb6207bffce9646978a6766d46cf0a1c3629c92822
        #          2bd6e00adb43344ac4196bca72b03ddac18d69d184e99186da07ceab2953d30fef30bff2d4752abfcb7ca
        # pub-sha1 5427ee66bcdbcc767b21600ec0db4c3cd96eba02
        # -----BEGIN PUBLIC KEY-----
        # MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQENjuYuBRfZtC3QTb9sdNpm9ti05RB
        # fxCzvjHZSsN3kmHia53eFBY2KgIdvfvFYW6IuL0Ptukk6JOhmS9TSYxAhrlvrgL5
        # 54wABkuSzuqcl8u2IHv/zpZGl4pnZtRs8KHDYpySgiK9bgCttDNErEGWvKcrA92s
        # GNadGE6ZGG2gfOqylT0w/vML/y1HUqv8t8o=
        # -----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b81040027038192000404363b98b8145f66d0b74136fdb1d3699" + \
                  "bdb62d394417f10b3be31d94ac3779261e26b9dde1416362a021dbdfbc5616e88b8bd0fb6e924e893a199" +\
                  "2f53498c4086b96fae02f9e78c00064b92ceea9c97cbb6207bffce9646978a6766d46cf0a1c3629c92822" + \
                  "2bd6e00adb43344ac4196bca72b03ddac18d69d184e99186da07ceab2953d30fef30bff2d4752abfcb7ca"
        master_key_hex = master_key.decode("HEX")
        master = dispersy.get_member(public_key=master_key_hex)
        return [master]
