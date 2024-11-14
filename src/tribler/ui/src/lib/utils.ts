import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"
import { category } from "@/models/torrent.model";
import TimeAgo from 'javascript-time-ago'
import en from 'javascript-time-ago/locale/en'
import es from 'javascript-time-ago/locale/es'
import pt from 'javascript-time-ago/locale/pt'
import ru from 'javascript-time-ago/locale/ru'
import zh from 'javascript-time-ago/locale/zh'
import { useTranslation } from "react-i18next";
import { triblerService } from "@/services/tribler.service";
import { FileLink, FileTreeItem } from "@/models/file.model";
import { CheckedState } from "@radix-ui/react-checkbox";
import JSZip from "jszip";

TimeAgo.setDefaultLocale(en.locale)
TimeAgo.addLocale(en)
TimeAgo.addLocale(es)
TimeAgo.addLocale(pt)
TimeAgo.addLocale(ru)
TimeAgo.addLocale(zh)


export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs))
}

export function capitalize(name: string) {
    return name[0].toUpperCase() + name.slice(1).toLowerCase();
}

export function unhexlify(input: string) {
    // Solution by SuperStormer @ https://stackoverflow.com/a/76241398
    return new TextDecoder().decode(new Uint8Array([...input.matchAll(/[0-9a-f]{2}/g)].map(a => parseInt(a[0], 16))));
};

export function getFilesFromMetainfo(metainfo: string) {
    const info = JSON.parse(unhexlify(metainfo))?.info || {};
    if (!info?.files) {
        return {
            files: [{ size: info.length, name: info.name, index: 0 }],
            name: info.name
        };
    }
    return {
        files: info.files.map((file: any, i: number) => ({ size: file.length, name: file.path.join('\\'), index: i })),
        name: info.name
    };
}

export function getMagnetLink(infohash: string, name: string): string {
    return `magnet:?xt=urn:btih:${infohash}&dn=${encodeURIComponent(name)}`;
}

export function categoryIcon(name: category): string {
    const categoryEmojis: Record<string, string> = {
        Video: '🎦',
        VideoClips: '📹',
        Audio: '🎧',
        Documents: '📝',
        'CD/DVD/BD': '📀',
        Compressed: '🗜',
        Games: '👾',
        Pictures: '📷',
        Books: '📚',
        Comics: '💢',
        Software: '💾',
        Science: '🔬',
        XXX: '💋',
        Other: '🤔',
    };
    return categoryEmojis[name] || '';
}

export function formatTimeAgo(ts: number) {
    let locale = triblerService.guiSettings.lang ?? 'en_US';
    const timeAg = new TimeAgo(locale.slice(0, 2));
    return timeAg.format(ts * 1000);
}

export function formatBytes(bytes: number) {
    if (bytes === 0) { return '0.00 B'; }
    const e = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, e)).toFixed(2) + ' ' + ' KMGTP'.charAt(e) + 'B';
}

export function formatTimeDiff(time: number) {
    if (time === 0) { return '-'; }
    const now = Date.now() / 1000;
    return formatTime(now - time);
}

export function formatTime(time: number) {
    if (time === 0) { return '-'; }
    const date = new Date(0);
    date.setSeconds(time);
    return date.toISOString().substr(11, 8);
}

export function formatFlags(flags: number[]) {
    const flagToString: Record<number, string> = {
        1: 'RELAY',
        2: 'EXIT_ANY',
        4: 'EXIT_IPV8',
        8: 'SPEEDTEST',
        32768: 'EXIT_HTTP'
    };
    let result = '';
    for (let flag of flags) {
        if (result) {
            result += ', ';
        }
        result = result + (flagToString[flag] || flag);
    }
    return result;
}

export function average(numbers: number[]) {
    return numbers.reduce((a, b) => a + b) / numbers.length;
}

export function median(numbers: number[]) {
    if (numbers.length === 0) { return 0; }

    numbers.sort((a, b) => a - b);

    const half = Math.floor(numbers.length / 2);

    if (numbers.length % 2) {
        return numbers[half];
    }
    return (numbers[half - 1] + numbers[half]) / 2.0;
}

export function getRowSelection(input: any[], selected_func: (item: any) => boolean) {
    let selection: Record<string, boolean> = {};
    for (const [index, item] of input.entries()) {
        selection[index.toString()] = selected_func(item);
    }
    return selection;
}

export function filterDuplicates(data: any[], key: string) {
    const seen = new Set();
    return data.filter(item => {
        const duplicate = seen.has(item[key]);
        seen.add(item[key]);
        return !duplicate;
    });
}

export const filesToTree = (files: FileTreeItem[], defaultName = "root", separator: string = '\\') => {
    if (files.length <= 1) {
        if (files.length == 1 && files[0].included == undefined)
            files[0].included = true;
        return files;
    }

    let result: any[] = [];
    let level = { result };

    files.forEach(file => {
        file.name.split(separator).reduce((r: any, name, i, a) => {
            if (!r[name]) {
                r[name] = { result: [] };
                r.result.push({ included: true, ...file, name, subRows: r[name].result })
            }
            return r[name];
        }, level)
    })

    files = [{
        index: -1,
        name: defaultName,
        size: 1,
        progress: 1,
        included: true,
        subRows: result,
    }];
    fixTreeProps(files[0]);
    return files;
}

export const fixTreeProps = (tree: FileTreeItem): { size: number, downloaded: number, included: CheckedState | undefined } => {
    if (tree.subRows && tree.subRows.length) {
        tree.size = tree.downloaded = 0;
        tree.included = undefined;
        for (const item of tree.subRows) {
            const { size, downloaded, included } = fixTreeProps(item);
            tree.size += size;
            tree.downloaded += downloaded;
            if (tree.included !== undefined)
                tree.included = tree.included == included ? included : 'indeterminate';
            else
                tree.included = included;
        }
        tree.progress = (tree.downloaded || 0) / tree.size;
    }
    return {
        size: tree.size,
        downloaded: tree.size * (tree.progress || 0),
        included: tree.included
    };
}

export const getSelectedFilesFromTree = (tree: FileTreeItem, included: boolean = true) => {
    const selectedFiles: number[] = [];
    if (tree.subRows && tree.subRows.length) {
        for (const item of tree.subRows) {
            for (const i of getSelectedFilesFromTree(item, included))
                selectedFiles.push(i);
        }
    }
    else if (tree.included === included)
        selectedFiles.push(tree.index);
    return selectedFiles;
}

export function downloadFile(file: FileLink) {
    var link = document.createElement("a");
    link.download = file.name;
    link.href = file.uri;
    link.click();
}

export async function downloadFilesAsZip(files: FileLink[], zipName: string) {
    const zip = new JSZip();
    for (let i = 0; i < files.length; i++) {
        const response = await fetch(files[i].uri);
        if (response.status != 200) continue;
        const blob = await response.blob();

        zip.file(files[i].name, blob);

        if (i == files.length - 1) {
            const zipData = await zip.generateAsync({ type: "blob" });
            const link = document.createElement("a");
            link.href = window.URL.createObjectURL(zipData);
            link.download = zipName;
            link.click();
        }
    }
}
