from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity


class HiddenTunnelCommunityMultichain(HiddenTunnelCommunity):

    @classmethod
    def get_master_members(cls, dispersy):
        # generated: Fri Jul 1 15:13:14 2016
        # curve: None
        # len: 571 bits ~ 144 bytes signature
        # pub: 170 3081a7301006072a8648ce3d020106052b810400270381920004029dccf1d327cda8ed59de2a3ffb4685
        # 64f386763f4981c2ad02c700f18fa2f3cc9ab3b49f07653358d511e989de156edd01bd27cfdda63ed28aefbbf8c42
        # 96cd2528c411c8f71340584c5290b4e9d67a98c8030ae6cb8b97c69ca3f3b63c0b548493b51df9f38b4f3302760ca
        # d2c89162ea42abcccf52af49029873565406ddab99f2aa71c6a5a1c9a653a27bc114a9
        # pub-sha1 bb2bd0302b9e6adb685009ef6ff29a6bdc9fb5cc
        # -----BEGIN PUBLIC KEY-----
        # MIGnMBAGByqGSM49AgEGBSuBBAAnA4GSAAQCnczx0yfNqO1Z3io/+0aFZPOGdj9JgcKtAscA8Y+i88yas7SfB2UzWNUR6Y
        # neFW7dAb0nz92mPtKK77v4xCls0lKMQRyPcTQFhMUpC06dZ6mMgDCubLi5fGnKPztjwLVISTtR3584tPMwJ2DK0siRYupC
        # q8zPUq9JAphzVlQG3auZ8qpxxqWhyaZTonvBFKk=
        # -----END PUBLIC KEY-----
        master_key = "3081a7301006072a8648ce3d020106052b810400270381920004029dccf1d327cda8ed59de2a3ffb4685" + \
                     "64f386763f4981c2ad02c700f18fa2f3cc9ab3b49f07653358d511e989de156edd01bd27cfdda63ed28aefbbf8c42" + \
                     "96cd2528c411c8f71340584c5290b4e9d67a98c8030ae6cb8b97c69ca3f3b63c0b548493b51df9f38b4f3302760ca" + \
                     "d2c89162ea42abcccf52af49029873565406ddab99f2aa71c6a5a1c9a653a27bc114a9"
        master_key_hex = master_key.decode("HEX")
        master = dispersy.get_member(public_key=master_key_hex)
        return [master]
