// For compile-time type checking and code completion

export interface Settings {
    api: {
        http_enabled: boolean;
        http_port: number;
        http_host: string;
        https_enabled: boolean;
        https_host: string;
        https_port: number;
        https_certfile: string;
        refresh_port_on_start: boolean;
        key: string;
    },
    ipv8: {
        interfaces: {
            interface: string;
            ip: string;
            port: number;
            worker_threads: number;
        }[];
        keys: {
            alias: string;
            generation: string;
            file: string;
        }[];
        logger: {
            level: string;
        }[];
        working_directory: string;
        walker_interval: number;
        overlay: {
            class: string;
            key: string;
            walkers: Object[]
            bootstrappers: Object[];
            initialize: Object;
            on_start: [string, Object][];
        };
    },
    statistics: boolean;
    content_discovery_community: {
        enabled: boolean;
    },
    database: {
        enabled: boolean;
    },
    dht_discovery: {
        enabled: boolean;
    },
    knowledge_community: {
        enabled: boolean;
    },
    libtorrent: {
        socks_listen_ports: number[];
        port: number;
        proxy_type: number;
        proxy_server: string;
        proxy_auth: string;
        max_connections_download: number;
        max_download_rate: number;
        max_upload_rate: number;
        utp: boolean;
        dht: boolean;
        dht_readiness_timeout: number;
        upnp: boolean;
        natpmp: boolean;
        lsd: boolean;
        download_defaults: {
            anonymity_enabled: boolean;
            number_hops: number;
            safeseeding_enabled: boolean;
            saveas: string;
            seeding_mode: string;
            seeding_ratio: number;
            seeding_time: number;
            channel_download: boolean;
            add_download_to_channel: boolean;
        },
    },
    rendezvous: {
        enabled: boolean;
    },
    torrent_checker: {
        enabled: boolean;
    },
    tunnel_community: {
        enabled: boolean;
        min_circuits: number;
        max_circuits: number;
    },
    user_activity: {
        enabled: boolean;
        max_query_history: number;
        health_check_interval: number;
    },
    state_dir: string;
    memory_db: boolean;
    ui: GuiSettings;
}

export interface GuiSettings {
    translation?: string;
    family_filter?: boolean;
    ask_download_settings?: boolean;
    disable_tags?: boolean;
    dev_mode?: boolean;
    lang?: string;
}
