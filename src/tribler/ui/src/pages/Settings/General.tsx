import { PathInput } from "@/components/path-input";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { GuiSettings, Settings } from "@/models/settings.model";
import { triblerService } from "@/services/tribler.service";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import SaveButton from "./SaveButton";


export default function General() {
    const { t } = useTranslation();
    const [settings, setSettings] = useState<Settings>();
    const [guiSettings, setGuiSettings] = useState<GuiSettings>();

    if (!settings) (async () => { setSettings(await triblerService.getSettings()) })();
    if (!guiSettings) setGuiSettings(triblerService.getGuiSettings());

    return (
        <div className="px-6 w-full">
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
                    checked={guiSettings?.ask_download_settings}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setGuiSettings({
                                ...settings,
                                ask_download_settings: !!value
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
                    checked={guiSettings?.family_filter}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setGuiSettings({
                                ...settings,
                                family_filter: !!value
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
                    checked={guiSettings?.disable_tags}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setGuiSettings({
                                ...settings,
                                disable_tags: !!value
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
                    if (guiSettings)
                        triblerService.setGuiSettings(guiSettings);
                    if (settings)
                        await triblerService.setSettings(settings);
                }}
            />
        </div>
    )
}
