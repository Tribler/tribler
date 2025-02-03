import { Download } from "@/models/download.model";
import { DownloadConfig } from "@/models/downloadconfig.model";
import { File as BTFile } from "@/models/file.model";
import { Path } from "@/models/path.model";
import { GuiSettings, Settings } from "@/models/settings.model";
import { Torrent } from "@/models/torrent.model";
import axios, { AxiosError, AxiosInstance } from "axios";
import { ErrorDict, formatAxiosError, handleHTTPError } from "./reporting";


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

    async getDownloads(infohash: string = '', getPeers: boolean = false, getPieces: boolean = false, getAvailability: boolean = false): Promise<undefined | ErrorDict | Download[]> {
        try {
            return (await this.http.get(`/downloads?infohash=${infohash}&get_peers=${+getPeers}&get_pieces=${+getPieces}&get_availability=${+getAvailability}`)).data.downloads;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getDownloadFiles(infohash: string): Promise<undefined | ErrorDict | BTFile[]> {
        try {
            return (await this.http.get(`/downloads/${infohash}/files`)).data.files;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async startDownload(uri: string, params: DownloadConfig = {}): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.put('/downloads', { ...params, uri: uri })).data.started;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async _mixSelectedIntoMetainfo(torrent: File, selected_files: number[] | undefined): Promise<Uint8Array> {
        // Read the torrent data from file
        const raw_bytes = new Uint8Array(await torrent.arrayBuffer());

        // Create the new data blocks
        const new_key = new Uint8Array([49, 52, 58, 115, 101, 108, 101, 99, 116, 101, 100, 95, 102, 105, 108, 101, 115])  // b"14:selected_files"
        if ((selected_files !== undefined) && (selected_files.length > 0)){
            const str_selected = selected_files.join('ei');
            var new_list = new Uint8Array(4 + str_selected.length);  // b"li" + str_selected + b"ee"
            new_list[0] = 108;  // b"l"
            new_list[1] = 105;  // b"i"
            new_list.set(str_selected.split('').map((c) => { return c.charCodeAt(0); }), 2);
            new_list[new_list.length - 2] = 101;  // b"e"
            new_list[new_list.length - 1] = 101;  // b"e"
        } else {
            var new_list = new Uint8Array([108, 101]);  // b"le"
        }

        // Merge everything into the output buffer
        const buf_len = raw_bytes.length + new_list.length + 17;  // (raw_bytes.length - 1) + 17 + new_list.length + 1
        const modified_data = new Uint8Array(buf_len);
        modified_data.set(raw_bytes, 0);
        modified_data.set(new_key, raw_bytes.length - 1);  // [!] this overwrites the last byte of raw_bytes
        modified_data.set(new_list, raw_bytes.length + 16);  // (raw_bytes.length - 1) + 17
        modified_data[buf_len - 1] = 101; // b"e"

        return modified_data;
    }

    async startDownloadFromFile(torrent: File, params: DownloadConfig = {}): Promise<undefined | ErrorDict | boolean> {
        try {
            // The way selected files are URL encoded leads to the pattern "&selected_files[]=<<FILE_NUMBER>>",
            // roughly 20 characters per file in a torrent. With the max of 8190 bytes for a URL, this will lead to
            // HTTP 400 errors for torrents that go over +- 400 files.
            return (await this.http.put('/downloads',
                                        await this._mixSelectedIntoMetainfo(torrent, params.selected_files), {
                                            params: {...params, "selected_files": []},
                                            headers: {
                                                'Content-Type': 'applications/x-bittorrent'
                                            }
                                        }
            )).data.started;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async stopDownload(infohash: string): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.patch(`/downloads/${infohash}`, { state: 'stop' })).data.modified;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async resumeDownload(infohash: string): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.patch(`/downloads/${infohash}`, { state: 'resume' })).data.modified;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async recheckDownload(infohash: string): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.patch(`/downloads/${infohash}`, { state: 'recheck' })).data.modified;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async moveDownload(infohash: string, dest_dir: string): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.patch(`/downloads/${infohash}`, { state: 'move_storage', dest_dir: dest_dir })).data.modified;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async setDownloadHops(infohash: string, anon_hops: number): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.patch(`/downloads/${infohash}`, { anon_hops: anon_hops })).data.modified;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async setDownloadFiles(infohash: string, selected_files: number[]): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.patch(`/downloads/${infohash}`, { selected_files: selected_files })).data.modified;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async removeDownload(infohash: string, removeData: boolean): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.delete(`/downloads/${infohash}`, { data: { remove_data: (removeData) ? 1 : 0 } })).data.removed;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async addDownloadTracker(infohash: string, trackerUrl: string): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.put(`/downloads/${infohash}/trackers`, { url: trackerUrl })).data.added;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async removeDownloadTracker(infohash: string, trackerUrl: string): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.delete(`/downloads/${infohash}/trackers`, { data: { url: trackerUrl } })).data.removed;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async forceCheckDownloadTracker(infohash: string, trackerUrl: string): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.put(`/downloads/${infohash}/tracker_force_announce`, { url: trackerUrl })).data.forced;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }

    }

    // Statistics

    async getIPv8Statistics(): Promise<undefined | ErrorDict | {total_up: number, total_down: number}> {
        try {
            return (await this.http.get('/statistics/ipv8')).data.ipv8_statistics;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getTriblerStatistics(): Promise<undefined | ErrorDict | {db_size: number, num_torrents: number}> {
        try {
            return (await this.http.get('/statistics/tribler')).data.tribler_statistics;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getLogs(): Promise<undefined | ErrorDict | string> {
        try {
            return (await this.http.get('/logging')).data;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    // Torrents / search

    async getMetainfo(uri: string, skipMagnet: boolean): Promise<undefined | ErrorDict | {metainfo: string, download_exists: boolean, valid_certificate: boolean}> {
        try {
            return (await this.http.get(`/torrentinfo?uri=${uri}&skipmagnet=${skipMagnet}`)).data;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getMetainfoFromFile(torrent: File): Promise<undefined | ErrorDict | {infohash: string, metainfo: string, download_exists: boolean}> {
        try {
            return (await this.http.put('/torrentinfo', torrent, {
                headers: {
                    'Content-Type': 'applications/x-bittorrent'
                }
            })).data;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getPopularTorrents(): Promise<undefined | ErrorDict | Torrent[]> {
        try {
            return (await this.http.get(`/metadata/torrents/popular?metadata_type=300&metadata_type=220&include_total=1&first=1&last=50`)).data.results;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getTorrentHealth(infohash: string): Promise<undefined | ErrorDict | { infohash: string, num_seeders: number, num_leechers: number, last_tracker_check: number }> {
        try {
            return (await this.http.get(`/metadata/torrents/${infohash}/health`)).data;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getCompletions(txt_filter: string): Promise<undefined | ErrorDict | string[]> {
        try {
            return (await this.http.get(`/metadata/search/completions?q=${txt_filter}`)).data.completions;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async searchTorrentsLocal(txt_filter: string): Promise<undefined | ErrorDict | Torrent[]> {
        try {
            return (await this.http.get(`/metadata/search/local?first=1&last=200&metadata_type=300&exclude_deleted=1&fts_text=${txt_filter}`)).data.results;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async searchTorrentsRemote(txt_filter: string, popular: boolean): Promise<undefined | ErrorDict | { request_uuid: string, peers: string[] }> {
        try {
            return (await this.http.put(`/search/remote?fts_text=${txt_filter}&popular=${+popular}&metadata_type=300&exclude_deleted=1`)).data;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    // Settings

    async getSettings(): Promise<undefined | ErrorDict | Settings> {
        try {
            const settings = (await this.http.get('/settings')).data.settings;
            this.guiSettings = {...settings?.ui, ...this.guiSettings};
            return settings
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async setSettings(settings: Partial<Settings>): Promise<undefined | ErrorDict | boolean> {
        try {
            this.guiSettings = {...this.guiSettings, ...settings?.ui};
            return (await this.http.post('/settings', settings)).data.modified;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getLibtorrentSession(hops: number): Promise<undefined | ErrorDict | { [s: string]: unknown; }> {
        try {
            return (await this.http.get(`/libtorrent/session?hop=${hops}`)).data.session;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getLibtorrentSettings(hops: number): Promise<undefined | ErrorDict | { [s: string]: unknown; }> {
        try {
            return (await this.http.get(`/libtorrent/settings?hop=${hops}`)).data.settings;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async updateRSS(urls: string[]): Promise<undefined | ErrorDict | { modified: boolean; }> {
        try {
            return (await this.http.put(`/rss`, {urls: urls})).data;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    // Versions
    async getVersion(): Promise<undefined | ErrorDict | string> {
        try {
            return (await this.http.get(`/versioning/versions/current`)).data.version;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getNewVersion(): Promise<undefined | ErrorDict | boolean> {
        try {
            const version_info_json = (await this.http.get(`/versioning/versions/check`)).data;
            return (version_info_json.has_version ? version_info_json.new_version : false);
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getVersions(): Promise<undefined | ErrorDict | {versions: string[], current: string}> {
        try {
            return (await this.http.get(`/versioning/versions`)).data;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async canUpgrade(): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.get(`/versioning/upgrade/available`)).data.can_upgrade;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async isUpgrading(): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.get(`/versioning/upgrade/working`)).data.running;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async performUpgrade(): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.post(`/versioning/upgrade`)).data.success;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async removeVersion(version_str: string): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.delete(`/versioning/versions/${version_str}`)).data.success;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    // Recommender

    async clickedResult(query: string, clicked: Torrent, results: Torrent[]): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.put(`/recommender/clicked`, {
                        query: query,
                        chosen_index: results.findIndex((e) => e.infohash == clicked.infohash),
                        timestamp: Date.now(),
                        results: results.map((x) => { return {
                            infohash: x.infohash,
                            seeders: x.num_seeders,
                            leechers: x.num_leechers
                        };})
                    })).data.added;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    // Misc

    async browseFiles(path: string, showFiles: boolean): Promise<undefined | ErrorDict | { current: string, paths: Path[], separator: string }> {
        try {
            return (await this.http.get(`/files/browse?path=${path}&files=${+showFiles}`)).data;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async listFiles(path: string, recursively: boolean): Promise<undefined | ErrorDict | { paths: Path[] }> {
        try {
            return (await this.http.get(`/files/list?path=${path}&recursively=${+recursively}`)).data;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async createDirectory(path: string, recursively: boolean): Promise<undefined | ErrorDict | { paths: Path[] }> {
        try {
            return (await this.http.get(`/files/create?path=${path}&recursively=${+recursively}`)).data;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async createTorrent(name: string, description: string, files: string[], exportDir: string, download: boolean): Promise<undefined | ErrorDict | { torrent: string }> {
        try {
            return (await this.http.post(`/createtorrent?download=${+download}`, {
                name: name,
                description: description,
                files: files,
                export_dir: exportDir
            })).data.torrent;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async shutdown(): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.put(`/shutdown`)).data.shutdown;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }
}

export const triblerService = new TriblerService();
