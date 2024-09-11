import { Circuit } from "@/models/circuit.model";
import { OverlayStats } from "@/models/overlay.model";
import axios, { AxiosInstance } from "axios";
import { handleHTTPError } from "./reporting";


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
        return (await this.http.put('/asyncio/drift', { enable })).data.success;
    }

    async getDrift() {
        return (await this.http.get('/asyncio/drift')).data.measurements;
    }

    async getTasks() {
        return (await this.http.get('/asyncio/tasks')).data.tasks;
    }

    async setAsyncioDebug(enable: boolean, slownessThreshold: number): Promise<boolean> {
        return (await this.http.put('/asyncio/debug', {enable: enable, slow_callback_duration: slownessThreshold})).data.success;
    }

    async getAsyncioDebug(): Promise<any> {
        return (await this.http.get('/asyncio/debug')).data;
    }

    async getOverlays() {
        return (await this.http.get('/overlays')).data.overlays;
    }

    async getOverlayStatistics(): Promise<OverlayStats[]> {
        return (await this.http.get('/overlays/statistics')).data.statistics;
    }

    async getTunnelPeers() {
        return (await this.http.get('/tunnel/peers')).data.peers;
    }

    async getCircuits(): Promise<Circuit[]> {
        return (await this.http.get('/tunnel/circuits')).data.circuits;
    }

    async getRelays() {
        return (await this.http.get('/tunnel/relays')).data.relays;
    }

    async getExits() {
        return (await this.http.get('/tunnel/exits')).data.exits;
    }

    async getSwarms() {
        return (await this.http.get('/tunnel/swarms')).data.swarms;
    }

    async getDHTStatistics() {
        return (await this.http.get('/dht/statistics')).data.statistics;
    }

    async getBuckets() {
        return (await this.http.get('/dht/buckets')).data.buckets;
    }

    async lookupDHTValue(hash: string) {
        return this.http.get(`/dht/values/${hash}`);
    }
}

export const ipv8Service = new IPv8Service();
