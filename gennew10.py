    def set_overlay_max_message_length(self,value):
        """ maximal messagelength over the secure overlay """
        self.sessconfig['overlay_max_message_length'] = value

    def get_overlay_max_message_length(self):
        return self.sessconfig['overlay_max_message_length']

    def set_download_help_dir(self,value):
        """ directory from download_help relative to state_dir """
        self.sessconfig['download_help_dir'] = value

    def get_download_help_dir(self):
        return self.sessconfig['download_help_dir']

    def set_bartercast(self,value):
        """ exchange upload/download statistics with peers """
        self.sessconfig['bartercast'] = value

    def get_bartercast(self):
        return self.sessconfig['bartercast']

    def set_superpeer_file(self,value):
        """ file with addresses of superpeers, relative to install_dir """
        self.sessconfig['superpeer_file'] = value

    def get_superpeer_file(self):
        return self.sessconfig['superpeer_file']

    def set_buddycast_collecting_solution(self,value):
        """ 1: simplest solution: per torrent/buddycasted peer/4hours, 2: tig for tag on group base """
        self.sessconfig['buddycast_collecting_solution'] = value

    def get_buddycast_collecting_solution(self):
        return self.sessconfig['buddycast_collecting_solution']

    def set_peer_icon_path(self,value):
        """ directory to store peer icons, relative to statedir """
        self.sessconfig['peer_icon_path'] = value

    def get_peer_icon_path(self):
        return self.sessconfig['peer_icon_path']

    def set_stop_collecting_threshold(self,value):
        """ stop collecting more torrents if the disk has less than this size (MB) """
        self.sessconfig['stop_collecting_threshold'] = value

    def get_stop_collecting_threshold(self):
        return self.sessconfig['stop_collecting_threshold']

sessdefaults = {}
sessdefaults['overlay_max_message_length'] = 8388608
sessdefaults['download_help_dir'] = torrent_help
sessdefaults['bartercast'] = 1
sessdefaults['superpeer_file'] = superpeer.txt
sessdefaults['buddycast_collecting_solution'] = 2
sessdefaults['peer_icon_path'] = icons
sessdefaults['stop_collecting_threshold'] = 200
