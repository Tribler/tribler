import json
from twisted.web import resource


class SettingsEndpoint(resource.Resource):

    isLeaf = True

    # Only contains the most necessary settings needed for the GUI
    def render_GET(self, request):

        settings_dict = {"settings": {
            "general": {
                "nickname": "Random nickname",
                "minport": 1337,
            },
            "video": {
                "enabled": True,
                "port": "-1",
            },
            "libtorrent": {
                "enabled": True,
                "lt_proxytype": 0,
                "lt_proxyserver": None,
                "lt_proxyauth": None,
                "utp": True,
            },
            "Tribler": {
                "saveas": "/Users/tribleruser/downloads",
                "showsaveas": 1,
                "default_number_hops": 1,
                "default_anonymity_enabled": True,
                "default_safeseeding_enabled": True,
                "maxuploadrate": 0,
                "maxdownloadrate": 0,
            },
            "watch_folder": {
                "enabled": True,
                "watch_folder_dir": "/Users/tribleruser/watchfolder",
            },
            "downloadconfig": {
                "seeding_mode": "ratio",
                "seeding_time": 60,
                "seeding_ratio": 2.0,
            },
            "multichain": {
                "enabled": True,
            },
            "tunnel_community": {
                "exitnode_enabled": True,
            },
        }}

        return json.dumps(settings_dict)

    # Do nothing when we are saving the settings
    def render_PUT(self, request):
        return json.dumps({"saved": True})
