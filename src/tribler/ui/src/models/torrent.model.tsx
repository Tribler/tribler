// For compile-time type checking and code completion


export type category = "Video" | "VideoClips" | "Audio" | "Documents"
    | "CD/DVD/BD" | "Compressed" | "Games" | "Pictures" | "Books"
    | "Comics" | "Software" | "Science" | "XXX" | "Other";

export interface Torrent {
    name: string;
    category: category;
    infohash: string;
    size: number;
    num_seeders: number;
    num_leechers: number;
    last_tracker_check: number;
    created: number;
    tag_processor_version: number;
    type: number;
    id: number;
    origin_id: number;
    public_key: string;
    status: number;
    statements: string[];
}
