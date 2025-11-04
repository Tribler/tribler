import {PathInput} from "@/components/path-input";
import {Checkbox} from "@/components/ui/checkbox";
import {Label} from "@/components/ui/label";
import {AutoManageSettings, Settings} from "@/models/settings.model";
import {triblerService} from "@/services/tribler.service";
import {isErrorDict} from "@/services/reporting";
import {useEffect, useState} from "react";
import {useTranslation} from "react-i18next";
import toast from "react-hot-toast";
import SaveButton from "./SaveButton";
import {Input} from "@/components/ui/input";
import {Textarea} from "@/components/ui/textarea";

const autoManageOptions = [
    {
        settingsKey: "active_downloads",
        translationKey: "ActiveDownloads",
        default: 3,
    },
    {
        settingsKey: "active_seeds",
        translationKey: "ActiveSeeds",
        default: 5,
    },
    {
        settingsKey: "active_checking",
        translationKey: "ActiveChecking",
        default: 1,
    },
    {
        settingsKey: "active_dht_limit",
        translationKey: "ActiveDHTLimit",
        default: 88,
    },
    {
        settingsKey: "active_tracker_limit",
        translationKey: "ActiveTrackerLimit",
        default: 1600,
    },
    {
        settingsKey: "active_lsd_limit",
        translationKey: "ActiveLSDLimit",
        default: 60,
    },
    {
        settingsKey: "active_limit",
        translationKey: "ActiveLimit",
        default: 500,
    },
];

export default function General() {
    const {t} = useTranslation();
    const [settings, setSettings] = useState<Settings>();
    const [moveCompleted, setMoveCompleted] = useState<boolean>(false);

    useEffect(() => {
        (async () => {
            const response = await triblerService.getSettings();
            if (response === undefined) {
                toast.error(`${t("ToastErrorGetSettings")} ${t("ToastErrorGenNetworkErr")}`);
            } else if (isErrorDict(response)) {
                toast.error(`${t("ToastErrorGetSettings")} ${response.error.message}`);
            } else {
                setSettings(response);
                setMoveCompleted((response?.libtorrent?.download_defaults?.completed_dir || "").length > 0);
            }
        })();
    }, []);

    return (
        <div className="p-5 w-full">
            <div className="pb-2 font-semibold">{t("WebServerSettings")}</div>
            <div className="py-2 flex items-center">
                <Label htmlFor="http_port" className="whitespace-nowrap pr-5">
                    {t("Port")}
                </Label>
                <Input
                    id="http_port"
                    className="w-40"
                    type="number"
                    min="0"
                    max="65535"
                    value={settings?.api ? settings?.api?.http_port : 0}
                    onChange={(event) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                api: {
                                    ...settings.api,
                                    http_port: +event.target.value,
                                },
                            });
                        }
                    }}
                />
            </div>
            <p className="text-xs p-0 pb-4 text-muted-foreground">{t("ZeroIsRandomPort")}</p>

            <div className="pt-5 py-2 font-semibold">{t("DefaultDownloadSettings")}</div>
            <div className="py-2 flex items-center">
                <Label htmlFor="saveas" className="whitespace-nowrap pr-5">
                    {t("SaveFilesTo")}
                </Label>
                <PathInput
                    path={settings?.libtorrent?.download_defaults?.saveas}
                    onPathChange={(path) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    download_defaults: {
                                        ...settings.libtorrent.download_defaults,
                                        saveas: path,
                                    },
                                },
                            });
                        }
                    }}
                />
            </div>
            <div className="py-2 flex items-center">
                <Label htmlFor="trackers_file" className="whitespace-nowrap pr-5">
                    {t("DefaultTrackersFile")}
                </Label>
                <PathInput
                    path={settings?.libtorrent?.download_defaults?.trackers_file}
                    directory={false}
                    onPathChange={(path) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    download_defaults: {
                                        ...settings.libtorrent.download_defaults,
                                        trackers_file: path,
                                    },
                                },
                            });
                        }
                    }}
                />
            </div>
            <div className="py-2 flex items-center">
                <Label htmlFor="torrent_folder" className="whitespace-nowrap pr-5">
                    {t("BackupTorrentFolder")}
                </Label>
                <PathInput
                    path={settings?.libtorrent?.download_defaults?.torrent_folder}
                    onPathChange={(path) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    download_defaults: {
                                        ...settings.libtorrent.download_defaults,
                                        torrent_folder: path,
                                    },
                                },
                            });
                        }
                    }}
                />
            </div>
            <div className="flex items-center">
                <div className="w-64 flex items-center">
                    <Checkbox
                        checked={moveCompleted}
                        id="move_completed"
                        onCheckedChange={(value) => setMoveCompleted(value === true)}
                    />
                    <label
                        htmlFor="move_completed"
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 whitespace-nowrap pl-2">
                        {t("MoveAfterCompletion")}
                    </label>
                </div>
                <PathInput
                    disabled={!moveCompleted}
                    path={settings?.libtorrent?.download_defaults?.completed_dir}
                    onPathChange={(path) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    download_defaults: {
                                        ...settings.libtorrent.download_defaults,
                                        completed_dir: path,
                                    },
                                },
                            });
                        }
                    }}
                />
            </div>

            <div className="flex items-center space-x-2 py-2">
                <Checkbox
                    checked={!!settings?.libtorrent?.check_after_complete}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    check_after_complete: !!value,
                                },
                            });
                        }
                    }}
                    id="check_after_complete"
                />
                <label
                    htmlFor="check_after_complete"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                    {t("CheckAfterCompletion")}
                </label>
            </div>

            <div className="flex items-center space-x-2 py-2">
                <Checkbox
                    checked={!!settings?.libtorrent?.ask_download_settings}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings?.libtorrent,
                                    ask_download_settings: !!value,
                                },
                            });
                        }
                    }}
                    id="anonymity_enabled"
                />
                <label
                    htmlFor="anonymity_enabled"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                    {t("AlwaysAsk")}
                </label>
            </div>
            <div className="flex items-center space-x-2 py-2">
                <Checkbox
                    checked={!!settings?.libtorrent?.download_defaults?.anonymity_enabled}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    download_defaults: {
                                        ...settings.libtorrent.download_defaults,
                                        anonymity_enabled: !!value,
                                    },
                                },
                            });
                        }
                    }}
                    id="anonymity_enabled"
                />
                <label
                    htmlFor="anonymity_enabled"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                    {t("DownloadAnon")}
                </label>
            </div>
            <div className="flex items-center space-x-2 py-2">
                <Checkbox
                    checked={!!settings?.libtorrent?.download_defaults?.safeseeding_enabled}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    download_defaults: {
                                        ...settings.libtorrent.download_defaults,
                                        safeseeding_enabled: !!value,
                                    },
                                },
                            });
                        }
                    }}
                    id="safeseeding_enabled"
                />
                <label
                    htmlFor="safeseeding_enabled"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                    {t("SeedAnon")}
                </label>
            </div>

            <div className="flex items-center space-x-2 py-2">
                <Checkbox
                    checked={!!settings?.libtorrent?.download_defaults?.auto_managed}
                    id="auto_manage"
                    onCheckedChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    download_defaults: {
                                        ...settings.libtorrent.download_defaults,
                                        auto_managed: !!value,
                                    },
                                },
                            });
                        }
                    }}
                />
                <label
                    htmlFor="auto_manage"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 whitespace-nowrap">
                    {t("AutoManageEnable")}
                </label>
            </div>

            <div className="space-x-2 py-2">
                <Label htmlFor="active_downloads" className="whitespace-nowrap">
                    {t("AutoManageMax")}
                </Label>
                <table className="border-separate border-spacing-2 items-center pt-2 pl-10 w-full">
                    <tbody>
                        {autoManageOptions.map((option) => (
                            <tr key={option.settingsKey}>
                                <td>
                                    <Label htmlFor="active_downloads" className="whitespace-nowrap">
                                        {t(option.translationKey)}
                                    </Label>
                                </td>
                                <td>
                                    <Input
                                        type="number"
                                        id={option.settingsKey}
                                        value={
                                            settings
                                                ? settings?.libtorrent[
                                                      option.settingsKey as keyof AutoManageSettings
                                                  ] || option.default
                                                : ""
                                        }
                                        onChange={(event) => {
                                            if (settings) {
                                                setSettings({
                                                    ...settings,
                                                    libtorrent: {
                                                        ...settings.libtorrent,
                                                        [option.settingsKey]: +event.target.value,
                                                    },
                                                });
                                            }
                                        }}
                                    />
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <div className="pt-5 py-2 font-semibold">{t("WatchFolder")}</div>
            <div className="flex items-center space-x-2 py-2">
                <Checkbox
                    checked={!!settings?.watch_folder?.enabled}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                watch_folder: {
                                    ...settings.watch_folder,
                                    enabled: !!value,
                                },
                            });
                        }
                    }}
                    id="watch_folder"
                />
                <label
                    htmlFor="watch_folder"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                    {t("EnableWatchFolder")}
                </label>
            </div>
            <div className="py-2 flex items-center">
                <Label htmlFor="saveas" className="whitespace-nowrap pr-5">
                    {t("TorrentWatchFolder")}
                </Label>
                <PathInput
                    path={settings?.watch_folder?.directory}
                    onPathChange={(path) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                watch_folder: {
                                    ...settings.watch_folder,
                                    directory: path,
                                },
                            });
                        }
                    }}
                />
            </div>

            <div className="py-2 flex items-center">
                <Label htmlFor="rss" className="whitespace-nowrap pr-5">
                    {"RSS:"}
                </Label>
                <Textarea
                    defaultValue={settings?.rss?.urls?.join?.("\n") ?? ""}
                    onChange={(elem) => {
                        var urls = elem.target.value.split("\n");
                        if (settings) {
                            setSettings({
                                ...settings,
                                rss: {
                                    ...settings.rss,
                                    urls: urls,
                                    enabled: !!urls,
                                },
                            });
                        }
                    }}
                />
            </div>

            <div className="pb-2 font-semibold">{t("Appearance") // Note: put this in its own tab if it grows too big
                }</div>
            <div className="py-2 flex items-center">
                <Label htmlFor="tray_color" className="whitespace-nowrap pr-5">
                    {t("TrayIconColor")}:
                </Label>
                <Checkbox id="tray_color_enabled" checked={!!settings?.tray_icon_color}
                    className="mr-10"
                    onCheckedChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                tray_icon_color: !!value ? "#E82901" : ""
                            });
                        }
                    }
                }/>
                <input type="color" id="tray_color" name="tray_color" value={settings?.tray_icon_color}
                    hidden={settings?.tray_icon_color === undefined || settings?.tray_icon_color == ""}
                    disabled={settings?.tray_icon_color === undefined || settings?.tray_icon_color == ""}
                    onChange={(evt) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                tray_icon_color: evt.target.value
                            });
                        }
                    }
                }/>
            </div>

            <SaveButton
                onClick={async () => {
                    if (settings) {
                        triblerService.updateRSS(settings.rss?.urls ? settings.rss.urls : []);
                        const response = await triblerService.setSettings({
                            ...settings,
                            libtorrent: {
                                ...settings.libtorrent,
                                download_defaults: {
                                    ...settings.libtorrent.download_defaults,
                                    completed_dir: moveCompleted
                                        ? settings.libtorrent.download_defaults.completed_dir
                                        : "",
                                },
                            },
                        });
                        if (response === undefined) {
                            toast.error(`${t("ToastErrorSetSettings")} ${t("ToastErrorGenNetworkErr")}`);
                        } else if (isErrorDict(response)) {
                            toast.error(`${t("ToastErrorSetSettings")} ${response.error.message}`);
                        }
                    }
                }}
            />
        </div>
    );
}
