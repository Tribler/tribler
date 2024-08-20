import { PathInput } from "@/components/path-input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Settings } from "@/models/settings.model";
import { triblerService } from "@/services/tribler.service";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import SaveButton from "./SaveButton";
import { Input } from "@/components/ui/input";


export default function General() {
    const { t } = useTranslation();
    const [settings, setSettings] = useState<Settings>();

    if (!settings) {
        (async () => { setSettings(await triblerService.getSettings()) })();
        return;
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

            <div className="pt-5 py-2 font-semibold">{t('FamilyFilter')}</div>
            <div className="flex items-center space-x-2 py-2">
                <Checkbox
                    checked={settings?.ui?.family_filter}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                ui: {
                                    ...settings?.ui,
                                    family_filter: !!value
                                }
                            });
                        }
                    }}
                    id="family_filter" />
                <label
                    htmlFor="family_filter"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                    {t('EnableFamilyFilter')}
                </label>
            </div>


            <div className="pt-5 py-2 font-semibold">{t('Tags')}</div>
            <div className="flex items-center space-x-2 py-2">
                <Checkbox
                    checked={settings?.ui?.disable_tags}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                ui: {
                                    ...settings?.ui,
                                    disable_tags: !!value
                                }
                            });
                        }
                    }}
                    id="disable_tags" />
                <label
                    htmlFor="disable_tags"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                    {t('HideTags')}
                </label>
            </div>

            <SaveButton
                onClick={async () => {
                    if (settings)
                        await triblerService.setSettings(settings);
                }}
            />
        </div>
    )
}
