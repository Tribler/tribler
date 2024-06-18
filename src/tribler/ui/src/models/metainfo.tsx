export interface Metainfo {
    info: {
        files: MetainfoFile[];
        name: string;
        "piece length": number;
        pieces: string;
    }
}

interface MetainfoFile {
    length: number;
    path: string[];

}