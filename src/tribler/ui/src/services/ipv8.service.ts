import { Circuit } from "@/models/circuit.model";
import { OverlayStats } from "@/models/overlay.model";
import axios, { AxiosInstance } from "axios";
import { handleHTTPError, handles } from "./reporting";


export class IPv8Service {
    private http: AxiosInstance;
    private baseURL = "/api/ipv8";

    constructor() {
        this.http = axios.create({
            baseURL: this.baseURL,
            withCredentials: true,
        });
    }


    async enableDrift(enable: boolean): Promise<boolean> {
        const response = await (this.http.put('/asyncio/drift', { enable: enable },
                                              handles(200, 400)).catch(handleHTTPError));
        if (response.status == 200)
            return response.data.success;
        return false;
    }

    async getDrift() {
        const response = await (this.http.get('/asyncio/drift', handles(200, 404)).catch(handleHTTPError));
        if (response.status == 200)
            return response.data.measurements;
        return [];
    }

    async getTasks() {
        return (await (this.http.get('/asyncio/tasks', handles(200)).catch(handleHTTPError))).data.tasks;
    }

    async setAsyncioDebug(enable: boolean, slownessThreshold: number): Promise<boolean> {
        const response = await (this.http.put('/asyncio/debug',
                                              {enable: enable, slow_callback_duration: slownessThreshold},
                                              handles(200)).catch(handleHTTPError))
        if (response.status == 200)
            return response.data.success;
        return false;
    }

    async getAsyncioDebug(): Promise<any> {
        return (await (this.http.get('/asyncio/debug', handles(200)).catch(handleHTTPError))).data;
    }

    async getOverlays() {
        return (await (this.http.get('/overlays', handles(200)).catch(handleHTTPError))).data.overlays;
    }

    async getOverlayStatistics(): Promise<OverlayStats[]> {
        return (await (this.http.get('/overlays/statistics', handles(200)).catch(handleHTTPError))).data.statistics;
    }

    async getTunnelPeers() {
        return (await (this.http.get('/tunnel/peers', handles(200)).catch(handleHTTPError))).data.peers;
    }

    async getCircuits(): Promise<Circuit[]> {
        return (await this.http.get('/tunnel/circuits')).data.circuits;
    }

    async getRelays() {
        return (await (this.http.get('/tunnel/relays', handles(200)).catch(handleHTTPError))).data.relays;
    }

    async getExits() {
        return (await (this.http.get('/tunnel/exits', handles(200)).catch(handleHTTPError))).data.exits;
    }

    async getSwarms() {
        return (await (this.http.get('/tunnel/swarms', handles(200)).catch(handleHTTPError))).data.swarms;
    }

    async getDHTStatistics() {
        return (await (this.http.get('/dht/statistics',
                                     handles(200)).catch(handleHTTPError))).data.statistics;  // Crash in case of 404
    }

    async getBuckets() {
        return (await (this.http.get('/dht/buckets', handles(200)).catch(handleHTTPError))).data.buckets;
    }

    async lookupDHTValue(hash: string) {
        return (await (this.http.get(`/dht/values/${hash}`,
                                     handles(200)).catch(handleHTTPError))).data;  // Crash in case of 404
    }
}

export const ipv8Service = new IPv8Service();
