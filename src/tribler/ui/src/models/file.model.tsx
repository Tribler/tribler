// For compile-time type checking and code completion

import { CheckedState } from "@radix-ui/react-checkbox";

export interface File {
    index: number;
    name: string;
    size: number;
    included: boolean;
    progress: number;
}

export interface FileTreeItem {
    index: number;
    name: string;
    size: number;
    downloaded?: number;
    progress?: number;
    included?: CheckedState;
    subRows?: FileTreeItem[];
}

export interface FileLink {
    uri: string;
    name: string;
}
