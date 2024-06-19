import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"
import { Torrent, category } from "@/models/torrent.model";
import TimeAgo from 'javascript-time-ago'
import en from 'javascript-time-ago/locale/en'
import es from 'javascript-time-ago/locale/es'
import pt from 'javascript-time-ago/locale/pt'
import ru from 'javascript-time-ago/locale/ru'
import zh from 'javascript-time-ago/locale/zh'
import Cookies from "js-cookie";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

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
    var result = '';
    for (var i = 0, l = input.length; i < l; i += 2) {
        result += String.fromCharCode(parseInt(input.slice(i, i + 2), 16));
    }
    return result;
};

export function getFilesFromMetainfo(metainfo: string) {
    const info = JSON.parse(unhexlify(metainfo))?.info || {};
    if (!info?.files) {
        return [{ length: info.length, path: info.name }];
    }
    return info.files.map((file: any) => (
        { length: file.length, path: file.path.join('\\') }
    ));
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
    let locale = Cookies.get('lang') ?? 'en-US';
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

export function translateHeader(name: string) {
    return () => {
        const { t } = useTranslation();
        return t(name);
    }
}
