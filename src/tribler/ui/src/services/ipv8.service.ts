import { Bucket, DHTStats, Values } from "@/models/bucket.model";
import { Circuit } from "@/models/circuit.model";
import { Drift } from "@/models/drift.model";
import { Exit } from "@/models/exit.model";
import { Overlay, OverlayStats } from "@/models/overlay.model";
import { Relay } from "@/models/relay.model";
import { Swarm } from "@/models/swarm.model";
import { Task } from "@/models/task.model";
import { Peer } from "@/models/tunnelpeer.model";
import axios, { AxiosError, AxiosInstance } from "axios";
import { ErrorDict, formatAxiosError, handleHTTPError } from "./reporting";


export class IPv8Service {
    private http: AxiosInstance;
    private baseURL = "/api/ipv8";

    constructor() {
        this.http = axios.create({
            baseURL: this.baseURL,
            withCredentials: true,
        });
    }


    async enableDrift(enable: boolean): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.put('/asyncio/drift', { enable })).data.success;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getDrift(): Promise<undefined | ErrorDict | Drift[]> {
        try {
            return (await this.http.get('/asyncio/drift')).data.measurements;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getTasks(): Promise<undefined | ErrorDict | Task[]> {
        try {
            return (await this.http.get('/asyncio/tasks')).data.tasks;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async setAsyncioDebug(enable: boolean, slownessThreshold: number): Promise<undefined | ErrorDict | boolean> {
        try {
            return (await this.http.put('/asyncio/debug', {enable: enable, slow_callback_duration: slownessThreshold})).data.success;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getAsyncioDebug(): Promise<undefined | ErrorDict | any> {
        try {
            return (await this.http.get('/asyncio/debug')).data;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getOverlays(): Promise<undefined | ErrorDict | Overlay[]> {
        try {
            return (await this.http.get('/overlays')).data.overlays;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getOverlayStatistics(): Promise<undefined | ErrorDict | OverlayStats[]> {
        try {
            return (await this.http.get('/overlays/statistics')).data.statistics;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getTunnelPeers(): Promise<undefined | ErrorDict | Peer[]> {
        try {
            return (await this.http.get('/tunnel/peers')).data.peers;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getCircuits(): Promise<undefined | ErrorDict | Circuit[]> {
        try {
            return (await this.http.get('/tunnel/circuits')).data.circuits;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getRelays(): Promise<undefined | ErrorDict | Relay[]> {
        try {
            return (await this.http.get('/tunnel/relays')).data.relays;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getExits(): Promise<undefined | ErrorDict | Exit[]> {
        try {
            return (await this.http.get('/tunnel/exits')).data.exits;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getSwarms(): Promise<undefined | ErrorDict | Swarm[]> {
        try {
            return (await this.http.get('/tunnel/swarms')).data.swarms;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getDHTStatistics(): Promise<undefined | ErrorDict | DHTStats> {
        try {
            return (await this.http.get('/dht/statistics')).data.statistics;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async getBuckets(): Promise<undefined | ErrorDict | Bucket[]> {
        try {
            return (await this.http.get('/dht/buckets')).data.buckets;
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }

    async lookupDHTValue(hash: string): Promise<undefined | ErrorDict | Values> {
        try {
            return this.http.get(`/dht/values/${hash}`);
        } catch (error) {
            return formatAxiosError(error as Error | AxiosError);
        }
    }
}

export const ipv8Service = new IPv8Service();
