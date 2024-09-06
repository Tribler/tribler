import { Download } from "@/models/download.model";
import { DownloadConfig } from "@/models/downloadconfig.model";
import { File as BTFile } from "@/models/file.model";
import { Path } from "@/models/path.model";
import { GuiSettings, Settings } from "@/models/settings.model";
import { Torrent } from "@/models/torrent.model";
import axios, { AxiosError, AxiosInstance } from "axios";
import { handleHTTPError, handles } from "./reporting";


const OnError = (event: MessageEvent) => {
    const data = JSON.parse(event.data);
    handleHTTPError(new Error(data.traceback));
};


export class TriblerService {
    private http: AxiosInstance;
    private baseURL = "/api";
    private events: EventSource;
    // Store a cached version of the GuiSettings to prevent from having to call the server every time we need them.
    public guiSettings: GuiSettings = {};

    constructor() {
        this.http = axios.create({
            baseURL: this.baseURL,
            withCredentials: true,
        });
        this.events = new EventSource(this.baseURL + '/events', { withCredentials: true });
        this.addEventListener("tribler_exception", OnError);
        // Gets the GuiSettings
        this.getSettings();
    }

    isOnline() {
        return this.events.readyState === this.events.OPEN;
    }

    // Events

    addEventListener(topic: string, listener: (event: MessageEvent) => void): void {
        this.events.addEventListener(topic, listener);
    }

    removeEventListener(topic: string, listener: (event: MessageEvent) => void): void {
        this.events.removeEventListener(topic, listener);
    }

    // Downloads

    async getDownloads(infohash: string = '', getPeers: boolean = false, getPieces: boolean = false): Promise<Download[]> {
        return (await (this.http.get(`/downloads?infohash=${infohash}&get_peers=${+getPeers}&get_pieces=${+getPieces}`,
                                     handles(200)).catch(handleHTTPError))).data.downloads;
    }

    async getDownloadFiles(infohash: string): Promise<BTFile[]> {
        const response = await (this.http.get(`/downloads/${infohash}/files`,
                                              handles(200, 404)).catch(handleHTTPError));
        if (response.status == 200)
            return response.data.files;
        return [];
    }

    async startDownload(uri: string, params: DownloadConfig = {}): Promise<boolean> {
        const response = await (this.http.put('/downloads', { ...params, uri: uri },
                                              handles(200, 400, 500)).catch(handleHTTPError));
        if (response.status == 200)
            return response.data.started;
        return false;
    }

    async startDownloadFromFile(torrent: File, params: DownloadConfig = {}): Promise<boolean> {
        const options = handles(200, 400, 500);
        options['params'] = params;
        options['headers'] = { 'Content-Type': 'applications/x-bittorrent' };
        const response = await (this.http.put('/downloads', torrent, options).catch(handleHTTPError));
        if (response.status == 200)
            return response.data.started;
        return false;
    }

    async stopDownload(infohash: string): Promise<boolean> {
        const response = await (this.http.patch(`/downloads/${infohash}`, { state: 'stop' },
                                                handles(200, 400, 404, 500)).catch(handleHTTPError));
        if (response.status == 200)
            return response.data.modified;
        return false;
    }

    async resumeDownload(infohash: string): Promise<boolean> {
        const response = await (this.http.patch(`/downloads/${infohash}`, { state: 'resume' },
                                                handles(200, 400, 404, 500)).catch(handleHTTPError));
        if (response.status == 200)
            return response.data.modified;
        return false;
    }

    async recheckDownload(infohash: string): Promise<boolean> {
        const response = await (this.http.patch(`/downloads/${infohash}`, { state: 'recheck' },
                                                handles(200, 400, 404, 500)).catch(handleHTTPError));
        if (response.status == 200)
            return response.data.modified;
        return false;
    }

    async moveDownload(infohash: string, dest_dir: string): Promise<boolean> {
        const response = await (this.http.patch(`/downloads/${infohash}`, { state: 'move_storage', dest_dir: dest_dir },
                                                handles(200, 400, 404, 500)).catch(handleHTTPError));
        if (response.status == 200)
            return response.data.modified;
        return false;
    }

    async setDownloadHops(infohash: string, anon_hops: number): Promise<boolean> {
        const response = await (this.http.patch(`/downloads/${infohash}`, { anon_hops: anon_hops },
                                                handles(200, 400, 404, 500)).catch(handleHTTPError));
        if (response.status == 200)
            return response.data.modified;
        return false;
    }

    async setDownloadFiles(infohash: string, selected_files: number[]): Promise<boolean> {
        const response = await (this.http.patch(`/downloads/${infohash}`, { selected_files: selected_files },
                                                handles(200, 400, 404, 500)).catch(handleHTTPError));
        if (response.status == 200)
            return response.data.modified;
        return false;
    }

    async removeDownload(infohash: string, removeData: boolean): Promise<boolean> {
        const options = handles(200, 400, 404);
        options['data'] = { remove_data: (removeData) ? 1 : 0 };
        const response = await (this.http.delete(`/downloads/${infohash}`, options).catch(handleHTTPError));
        if (response.status == 200)
            return response.data.removed;
        return false;
    }

    // Statistics

    async getIPv8Statistics() {
        return (await (this.http.get('/statistics/ipv8', handles(200)))).data.ipv8_statistics;
    }

    async getTriblerStatistics() {
        return (await (this.http.get('/statistics/tribler', handles(200)))).data.tribler_statistics;
    }

    // Torrents / search

    async getMetainfo(uri: string) {
        return (await (this.http.get(`/torrentinfo?uri=${uri}`, handles(200, 400, 500)).catch(handleHTTPError))).data;
    }

    async getMetainfoFromFile(torrent: File) {
        var options = handles(200);
        options['headers'] = { 'Content-Type': 'applications/x-bittorrent' };
        return (await (this.http.put('/torrentinfo', torrent, options).catch(handleHTTPError))).data;
    }

    async getPopularTorrents(hide_xxx: boolean): Promise<Torrent[]> {
        return (await (this.http.get(`/metadata/torrents/popular?metadata_type=300&metadata_type=220&include_total=1&first=1&last=50&hide_xxx=${+hide_xxx}`,
                                     handles(200)).catch(handleHTTPError))).data.results;
    }

    async getTorrentHealth(infohash: string): Promise<{ infohash: string, num_seeders: number, num_leechers: number, last_tracker_check: number }> {
        // TODO: The return value seems wrong. (200) => {'checking': bool} or (400) => {'error': string}
        return (await (this.http.get(`/metadata/torrents/${infohash}/health`,
                                     handles(200, 400)).catch(handleHTTPError))).data;
    }

    async getCompletions(txt_filter: string): Promise<string[]> {
        const response = await (this.http.get(`/metadata/search/completions?q=${txt_filter}`,
                                              handles(200, 400)).catch(handleHTTPError));
        if (response.status == 200)
            return response.data.completions;
        return [];
    }

    async searchTorrentsLocal(txt_filter: string, hide_xxx: boolean): Promise<Torrent[]> {
        const response = await (this.http.get(`/metadata/search/local?first=1&last=200&metadata_type=300&exclude_deleted=1&fts_text=${txt_filter}&hide_xxx=${+hide_xxx}`,
                                              handles(200, 400, 404)).catch(handleHTTPError));
        if (response.status == 200)
            return response.data.results;
        return [];
    }

    async searchTorrentsRemote(txt_filter: string, hide_xxx: boolean): Promise<{ request_uuid: string, peers: string[] }> {
        return (await (this.http.put(`/search/remote?fts_text=${txt_filter}&hide_xxx=${+hide_xxx}&metadata_type=300&exclude_deleted=1`,
                                    undefined, handles(200)).catch(handleHTTPError))).data;  // Crash in case of 400
    }

    // Settings

    async getSettings(): Promise<Settings> {
        const settings = (await (this.http.get('/settings', handles(200)).catch(handleHTTPError))).data.settings;
        this.guiSettings = {...settings?.ui, ...this.guiSettings};
        return settings
    }

    async setSettings(settings: Partial<Settings>): Promise<boolean> {
        this.guiSettings = {...settings?.ui, ...this.guiSettings};
        return (await (this.http.post('/settings', settings, handles(200)).catch(handleHTTPError))).data.modified;
    }

    async getLibtorrentSession(hops: number) {
        return (await (this.http.get(`/libtorrent/session?hop=${hops}`,
                                     handles(200)).catch(handleHTTPError))).data.session;
    }

    async getLibtorrentSettings(hops: number) {
        return (await (this.http.get(`/libtorrent/settings?hop=${hops}`,
                                     handles(200)).catch(handleHTTPError))).data.settings;
    }

    // Versions
    async getVersion() {
        return (await (this.http.get(`/versioning/versions/current`,
                                     handles(200)).catch(handleHTTPError))).data.version;
    }

    async getNewVersion() {
        const version_info_json = (await (this.http.get(`/versioning/versions/check`,
                                     handles(200)).catch(handleHTTPError))).data;
        return (version_info_json.has_version ? version_info_json.new_version : false);
    }

    async getVersions() {
        return (await (this.http.get(`/versioning/versions`, handles(200)).catch(handleHTTPError))).data;
    }

    async canUpgrade() {
        return (await (this.http.get(`/versioning/upgrade/available`,
                                     handles(200)).catch(handleHTTPError))).data.can_upgrade;
    }

    async isUpgrading() {
        return (await (this.http.get(`/versioning/upgrade/working`, handles(200)).catch(handleHTTPError))).data.running;
    }

    async performUpgrade() {
        return await (this.http.post(`/versioning/upgrade`, undefined, handles(200)).catch(handleHTTPError));
    }

    async removeVersion(version_str: string): Promise<boolean> {
        const response = await (this.http.delete(`/versioning/versions/${version_str}`,
                                handles(200, 400)).catch(handleHTTPError));
        if (response.status == 200)
            return response.data.success;
        return false;
    }

    // Misc

    async browseFiles(path: string, showFiles: boolean): Promise<{ current: string, paths: Path[] }> {
        return (await (this.http.get(`/files/browse?path=${path}&files=${+showFiles}`,
                                     handles(200)).catch(handleHTTPError))).data;
    }

    async listFiles(path: string, recursively: boolean): Promise<{ paths: Path[] }> {
        return (await (this.http.get(`/files/list?path=${path}&recursively=${+recursively}`,
                                     handles(200)).catch(handleHTTPError))).data;
    }

    async createTorrent(name: string, description: string, files: string[], exportDir: string, download: boolean) {
        return (await (this.http.post(`/createtorrent?download=${+download}`, {
                                          name: name,
                                          description: description,
                                          files: files,
                                          export_dir: exportDir
                                      }, handles(200)).catch(handleHTTPError))).data.torrent;  // Crash in case of 400
    }

    async shutdown(): Promise<boolean> {
        return (await (this.http.put(`/shutdown`, undefined, handles(200)).catch(handleHTTPError))).data.shutdown;
    }
}

export const triblerService = new TriblerService();
