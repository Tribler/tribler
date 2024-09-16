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

    async getDownloads(infohash: string = '', getPeers: boolean = false, getPieces: boolean = false): Promise<undefined | ErrorDict | Download[]> {
        try {
            return (await this.http.get(`/downloads?infohash=${infohash}&get_peers=${+getPeers}&get_pieces=${+getPieces}`)).data.downloads;
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

    async startDownloadFromFile(torrent: File, params: DownloadConfig = {}): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.put('/downloads', torrent, {
                params: params,
                headers: {
                    'Content-Type': 'applications/x-bittorrent'
                }
            })).data.started;
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

    // Torrents / search

    async getMetainfo(uri: string): Promise<undefined | ErrorDict | {metainfo: string, download_exists: boolean}> {
        try {
            return (await this.http.get(`/torrentinfo?uri=${uri}`)).data;
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
            this.guiSettings = {...settings?.ui, ...this.guiSettings};
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

    // Misc

    async browseFiles(path: string, showFiles: boolean): Promise<undefined | ErrorDict | { current: string, paths: Path[] }> {
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
