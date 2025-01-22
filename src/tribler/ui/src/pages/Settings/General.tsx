import { PathInput } from "@/components/path-input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Settings } from "@/models/settings.model";
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from 'react-hot-toast';
import SaveButton from "./SaveButton";
import { Input } from "@/components/ui/input";


export default function General() {
    const { t } = useTranslation();
    const [settings, setSettings] = useState<Settings>();
    const [moveCompleted, setMoveCompleted] = useState<boolean>(false);

    if (!settings) {
        (async () => {
            const response = await triblerService.getSettings();
            if (response === undefined) {
                toast.error(`${t("ToastErrorGetSettings")} ${t("ToastErrorGenNetworkErr")}`);
            } else if (isErrorDict(response)) {
                toast.error(`${t("ToastErrorGetSettings")} ${response.error.message}`);
            } else {
                setSettings(response);
                setMoveCompleted((response?.libtorrent?.download_defaults?.completed_dir || '').length > 0)
            }
        })();
        return null;
    }

    return (
        <div className="px-6 w-full">
            <div className="pt-5 py-2 font-semibold">{t('WebServerSettings')}</div>
            <div className="py-2 flex items-center">
                <Label htmlFor="http_port" className="whitespace-nowrap pr-5">
                    {t('Port')}
                </Label>
                <Input
                    id="http_port"
                    className="w-40"
                    type="number"
                    min="0"
                    max="65535"
                    value={settings?.api?.http_port}
                    onChange={(event) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                api: {
                                    ...settings.api,
                                    http_port: +event.target.value
                                }
                            });
                        }
                    }}
                />
            </div>
            <p className="text-xs p-0 pb-4 text-muted-foreground">{t('ZeroIsRandomPort')}</p>

            <div className="pt-5 py-2 font-semibold">{t('DefaultDownloadSettings')}</div>
            <div className="py-2 flex items-center">
                <Label htmlFor="saveas" className="whitespace-nowrap pr-5">
                    {t('SaveFilesTo')}
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
                                        saveas: path
                                    }
                                }
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
                        onCheckedChange={(value) => setMoveCompleted(value === true)} />
                    <label
                        htmlFor="move_completed"
                        className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 whitespace-nowrap pl-2"
                    >
                        {t('MoveAfterCompletion')}
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
                                        completed_dir: path
                                    }
                                }
                            });
                        }
                    }}
                />
            </div>

            <div className="flex items-center space-x-2 py-2">
                <Checkbox
                    checked={settings?.ui?.ask_download_settings}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                ui: {
                                    ...settings?.ui,
                                    ask_download_settings: !!value
                                }
                            });
                        }
                    }}
                    id="anonymity_enabled" />
                <label
                    htmlFor="anonymity_enabled"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                    {t('AlwaysAsk')}
                </label>
            </div>
            <div className="flex items-center space-x-2 py-2">
                <Checkbox
                    checked={settings?.libtorrent?.download_defaults?.anonymity_enabled}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    download_defaults: {
                                        ...settings.libtorrent.download_defaults,
                                        anonymity_enabled: !!value
                                    }
                                }
                            });
                        }
                    }}
                    id="anonymity_enabled" />
                <label
                    htmlFor="anonymity_enabled"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                    {t('DownloadAnon')}
                </label>
            </div>
            <div className="flex items-center space-x-2 py-2">
                <Checkbox
                    checked={settings?.libtorrent?.download_defaults?.safeseeding_enabled}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    download_defaults: {
                                        ...settings.libtorrent.download_defaults,
                                        safeseeding_enabled: !!value
                                    }
                                }
                            });
                        }
                    }}
                    id="safeseeding_enabled" />
                <label
                    htmlFor="safeseeding_enabled"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                    {t('SeedAnon')}
                </label>
            </div>

            <div className="pt-5 py-2 font-semibold">{t('WatchFolder')}</div>
            <div className="flex items-center space-x-2 py-2">
                <Checkbox
                    checked={settings?.watch_folder?.enabled}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                watch_folder: {
                                    ...settings.watch_folder,
                                    enabled: !!value
                                }
                            });
                        }
                    }}
                    id="watch_folder" />
                <label
                    htmlFor="watch_folder"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                    {t('EnableWatchFolder')}
                </label>
            </div>
            <div className="py-2 flex items-center">
                <Label htmlFor="saveas" className="whitespace-nowrap pr-5">
                    {t('TorrentWatchFolder')}
                </Label>
                <PathInput
                    path={settings?.watch_folder?.directory}
                    onPathChange={(path) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                watch_folder: {
                                    ...settings.watch_folder,
                                    directory: path
                                }
                            });
                        }
                    }}
                />
            </div>

            <SaveButton
                onClick={async () => {
                    if (settings) {
                        const response = await triblerService.setSettings({
                            ...settings,
                            libtorrent: {
                                ...settings.libtorrent,
                                download_defaults: {
                                    ...settings.libtorrent.download_defaults,
                                    completed_dir: moveCompleted ? settings.libtorrent.download_defaults.completed_dir : ''
                                }
                            }
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
    )
}
