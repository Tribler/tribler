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
    };
    ipv8: {
        interfaces: {
            interface: string;
            ip: string;
            port: number;
            worker_threads?: number;
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
            walkers: Object[];
            bootstrappers: Object[];
            initialize: Object;
            on_start: [string, Object][];
        };
    };
    statistics: boolean;
    content_discovery_community: {
        enabled: boolean;
    };
    database: {
        enabled: boolean;
    };
    dht_discovery: {
        enabled: boolean;
    };
    libtorrent: {
        socks_listen_ports: number[];
        listen_interface: string;
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
        announce_to_all_tiers: boolean;
        announce_to_all_trackers: boolean;
        max_concurrent_http_announces: number;
        check_after_complete: boolean;
        ask_download_settings: boolean;
        download_defaults: {
            anonymity_enabled: boolean;
            number_hops: number;
            safeseeding_enabled: boolean;
            saveas: string;
            completed_dir: string;
            seeding_mode: string;
            seeding_ratio: number;
            seeding_time: number;
            channel_download: boolean;
            add_download_to_channel: boolean;
            trackers_file: string;
            torrent_folder: string;
            auto_managed: boolean;
        };
    } & AutoManageSettings;
    rendezvous: {
        enabled: boolean;
    };
    rss: {
        enabled: boolean;
        urls: string[];
    };
    torrent_checker: {
        enabled: boolean;
    };
    tunnel_community: {
        enabled: boolean;
        min_circuits: number;
        max_circuits: number;
    };
    versioning: {
        enabled: boolean;
        allow_pre: boolean;
    }
    watch_folder: {
        enabled: boolean;
        directory: string;
        check_interval: number;
    };
    state_dir: string;
    memory_db: boolean;
    tray_icon_color: string;
    ui: GuiSettings;
}

export interface AutoManageSettings {
    active_downloads: number;
    active_seeds: number;
    active_checking: number;
    active_dht_limit: number;
    active_tracker_limit: number;
    active_lsd_limit: number;
    active_limit: number;
}

export interface GuiSettings {
    translation?: string;
    dev_mode?: boolean;
    lang?: string;
    theme?: string;
    sorting?: string;
    columns?: string;
}
