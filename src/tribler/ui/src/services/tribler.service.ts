import { Download } from "@/models/download.model";
import { DownloadConfig } from "@/models/downloadconfig.model";
import { File as BTFile } from "@/models/file.model";
import { Path } from "@/models/path.model";
import { GuiSettings, Settings } from "@/models/settings.model";
import { Torrent } from "@/models/torrent.model";
import axios, { AxiosInstance } from "axios";


export class TriblerService {
    private http: AxiosInstance;
    private baseURL = "/api";
    private events: EventSource;

    constructor() {
        this.http = axios.create({
            baseURL: this.baseURL,
            withCredentials: true,
        });
        this.events = new EventSource(this.baseURL + '/events', { withCredentials: true })
    }

    isOnline() {
        return this.events.readyState === this.events.OPEN;
    }

    // Events

    addEventListener(topic:string, listener: (event: MessageEvent) => void): void {
        this.events.addEventListener(topic, listener);
    }

    removeEventListener(topic:string, listener: (event: MessageEvent) => void): void {
        this.events.removeEventListener(topic, listener);
    }

    // Downloads

    async getDownloads(infohash: string = '', getPeers: boolean = false, getPieces: boolean = false): Promise<Download[]> {
        return (await this.http.get(`/downloads?infohash=${infohash}&get_peers=${+getPeers}&get_pieces=${+getPieces}`)).data.downloads;
    }

    async getDownloadFiles(infohash: string): Promise<BTFile[]> {
        return (await this.http.get(`/downloads/${infohash}/files`)).data.files;
    }

    async startDownload(uri: string, params: DownloadConfig = {}): Promise<boolean> {
        return (await this.http.put('/downloads', { ...params, uri: uri })).data.started;
    }

    async startDownloadFromFile(torrent: File, params: DownloadConfig = {}): Promise<boolean> {
        return (await this.http.put('/downloads', torrent, {
            params: params,
            headers: {
                'Content-Type': 'applications/x-bittorrent'
            }
        })).data.started;
    }

    async stopDownload(infohash: string): Promise<boolean> {
        const response = await this.http.patch(`/downloads/${infohash}`, { state: 'stop' });
        return response.data.modified;
    }

    async resumeDownload(infohash: string): Promise<boolean> {
        const response = await this.http.patch(`/downloads/${infohash}`, { state: 'resume' });
        return response.data.modified;
    }

    async recheckDownload(infohash: string): Promise<boolean> {
        const response = await this.http.patch(`/downloads/${infohash}`, { state: 'recheck' });
        return response.data.modified;
    }

    async moveDownload(infohash: string, dest_dir: string): Promise<boolean> {
        const response = await this.http.patch(`/downloads/${infohash}`, { state: 'move_storage', dest_dir: dest_dir });
        return response.data.modified;
    }

    async setDownloadHops(infohash: string, anon_hops: number): Promise<boolean> {
        const response = await this.http.patch(`/downloads/${infohash}`, { anon_hops: anon_hops });
        return response.data.modified;
    }

    async setDownloadFiles(infohash: string, selected_files: number[]): Promise<boolean> {
        const response = await this.http.patch(`/downloads/${infohash}`, { selected_files: selected_files });
        return response.data.modified;
    }

    async removeDownload(infohash: string, removeData: boolean): Promise<boolean> {
        const response = await this.http.delete(`/downloads/${infohash}`, { data: { remove_data: (removeData) ? 1 : 0 } });
        return await response.data.removed;
    }

    // Statistics

    async getIPv8Statistics() {
        return (await this.http.get('/statistics/ipv8')).data.ipv8_statistics;
    }

    async getTriblerStatistics() {
        return (await this.http.get('/statistics/tribler')).data.tribler_statistics;
    }

    // Torrents / search

    async getMetainfo(uri: string) {
        try {
            return (await this.http.get(`/torrentinfo?uri=${uri}`)).data;
        }
        catch (error) {
            if (axios.isAxiosError(error)) {
                return error.response?.data;
            }
        }
    }

    async getMetainfoFromFile(torrent: File) {
        return (await this.http.put('/torrentinfo', torrent, {
            headers: {
                'Content-Type': 'applications/x-bittorrent'
            }
        })).data;
    }

    async getPopularTorrents(hide_xxx: boolean): Promise<Torrent[]> {
        return (await this.http.get(`/metadata/torrents/popular?metadata_type=300&metadata_type=220&include_total=1&first=1&last=50&hide_xxx=${+hide_xxx}`)).data.results;
    }

    async getTorrentHealth(infohash: string): Promise<{infohash: string, num_seeders: number, num_leechers: number, last_tracker_check: number}> {
        return (await this.http.get(`/metadata/torrents/${infohash}/health`)).data;
    }

    async getCompletions(txt_filter: string): Promise<string[]> {
        return (await this.http.get(`/metadata/search/completions?q=${txt_filter}`)).data.completions;
    }

    async searchTorrentsLocal(txt_filter: string, hide_xxx: boolean): Promise<Torrent[]> {
        return (await this.http.get(`/metadata/search/local?first=1&last=200&metadata_type=300&exclude_deleted=1&fts_text=${txt_filter}&hide_xxx=${+hide_xxx}`)).data.results;
    }

    async searchTorrentsRemote(txt_filter: string, hide_xxx: boolean): Promise<{ request_uuid: string, peers: string[] }> {
        return (await this.http.put(`/search/remote?fts_text=${txt_filter}&hide_xxx=${+hide_xxx}&metadata_type=300&exclude_deleted=1`)).data;
    }

    // Settings

    async getSettings(): Promise<Settings> {
        return (await this.http.get('/settings')).data.settings;
    }

    async setSettings(settings: Settings): Promise<boolean> {
        return (await this.http.post('/settings', settings)).data.modified;
    }

    getGuiSettings(): GuiSettings {
        const settings_json = localStorage.getItem("gui_settings") ?? '{"ask_download_settings": true}';
        const settings: GuiSettings = JSON.parse(settings_json);
        return settings
    }

    setGuiSettings(settings: GuiSettings) {
        const settings_json = JSON.stringify(settings);
        localStorage.setItem("gui_settings", settings_json);
    }

    async getLibtorrentSession(hops: number) {
        return (await this.http.get(`/libtorrent/session?hop=${hops}`)).data.session;
    }

    async getLibtorrentSettings(hops: number) {
        return (await this.http.get(`/libtorrent/settings?hop=${hops}`)).data.settings;
    }

    // Misc

    async browseFiles(path: string, showFiles: boolean): Promise<{ current: string, paths: Path[] }> {
        return (await this.http.get(`/files/browse?path=${path}&files=${+showFiles}`)).data;
    }

    async listFiles(path: string, recursively: boolean): Promise<{ paths: Path[] }> {
        return (await this.http.get(`/files/list?path=${path}&recursively=${+recursively}`)).data;
    }

    async createTorrent(name: string, description: string, files: string[], exportDir: string, download: boolean) {
        return (await this.http.post(`/createtorrent?download=${+download}`, {
            name: name,
            description: description,
            files: files,
            export_dir: exportDir
        })).data.torrent;
    }

    async shutdown(): Promise<boolean> {
        return (await this.http.put(`/shutdown`)).data.shutdown;

    }
}

export const triblerService = new TriblerService();
