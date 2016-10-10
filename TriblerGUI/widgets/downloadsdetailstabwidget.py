from PyQt5.QtWidgets import QTabWidget, QTreeWidgetItem
from TriblerGUI.defs import *
from TriblerGUI.utilities import format_size, format_speed


class DownloadsDetailsTabWidget(QTabWidget):

    def update_with_download(self, download):
        self.window().download_detail_name_label.setText(download['name'])
        self.window().download_detail_status_label.setText(DLSTATUS_STRINGS[eval(download["status"])])
        self.window().download_detail_filesize_label.setText("%s in %d files" % (format_size(float(download["size"])), len(download["files"])))
        self.window().download_detail_health_label.setText("%d seeders, %d leechers" % (download["num_seeds"], download["num_peers"]))
        self.window().download_detail_infohash_label.setText(download['infohash'])
        self.window().download_detail_availability_label.setText("%.2f" % download['availability'])

        # Populate the files list
        self.window().download_files_list.clear()
        for file in download["files"]:
            item = QTreeWidgetItem(self.window().download_files_list)
            item.setText(0, file["name"])
            item.setText(1, format_size(float(file["size"])))
            item.setText(2, '{percent:.1%}'.format(percent=file["progress"]))
            item.setText(3, "yes" if file["included"] else "no")
            self.window().download_files_list.addTopLevelItem(item)

        # Populate the trackers list
        self.window().download_trackers_list.clear()
        for tracker in download["trackers"]:
            item = QTreeWidgetItem(self.window().download_trackers_list)
            item.setText(0, tracker["url"])
            item.setText(1, tracker["status"])
            item.setText(2, str(tracker["peers"]))

        # Populate the peers list if the peer information is available
        self.window().download_peers_list.clear()
        if "peers" in download:
            for peer in download["peers"]:
                self.create_widget_with_peer_info(peer)

    def create_widget_with_peer_info(self, peer):
        item = QTreeWidgetItem(self.window().download_peers_list)

        peer_name = "%s:%s" % (peer["ip"], peer["port"])
        if peer['connection_type'] == 1:
            peer_name += ' [WebSeed]'
        elif peer['connection_type'] == 2:
            peer_name += ' [HTTP Seed]'
        elif peer['connection_type'] == 3:
            peer_name += ' [uTP]'

        state = ""
        if peer['optimistic']:
            state += "O,"
        if peer['uinterested']:
            state += "UI,"
        if peer['uchoked']:
            state += "UC,"
        if peer['uhasqueries']:
            state += "UQ,"
        if not peer['uflushed']:
            state += "UBL,"
        if peer['ueligable']:
            state += "UE,"
        if peer['dinterested']:
            state += "DI,"
        if peer['dchoked']:
            state += "DC,"
        if peer['snubbed']:
            state += "S,"
        state += peer['direction']

        item.setText(0, peer_name)
        item.setText(1, '%d%%' % (peer['completed'] * 100.0))
        item.setText(2, format_speed(peer['downrate']))
        item.setText(3, format_speed(peer['uprate']))
        item.setText(4, state)
        item.setText(5, peer['extended_version'])
