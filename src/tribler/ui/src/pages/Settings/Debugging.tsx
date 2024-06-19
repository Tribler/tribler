import { Checkbox } from "@/components/ui/checkbox";
import { GuiSettings, Settings } from "@/models/settings.model";
import { triblerService } from "@/services/tribler.service";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import SaveButton from "./SaveButton";


export default function Debugging() {
    const { t } = useTranslation();
    const [settings, setSettings] = useState<Settings>();
    const [guiSettings, setGuiSettings] = useState<GuiSettings>();

    if (!settings) (async () => { setSettings(await triblerService.getSettings()) })();
    if (!guiSettings) setGuiSettings(triblerService.getGuiSettings());

    return (
        <div className="p-6">
            <div className="flex items-center space-x-2 p-2">
                <Checkbox
                    checked={guiSettings?.dev_mode === true}
                    onCheckedChange={(value) => {
                        if (guiSettings) {
                            setGuiSettings({
                                ...guiSettings,
                                dev_mode: !!value
                            })

                        }
                    }}
                    id="dev_mode" />
                <label
                    htmlFor="dev_mode"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                    {t('EnableDevMode')}
                </label>
            </div>
            <div className="flex items-center space-x-2 p-2">
                <Checkbox
                    checked={settings?.statistics}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                statistics: !!value,
                            });
                        }
                    }}
                    id="statistics" />
                <label
                    htmlFor="statistics"
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                    {t('EnableStats')}
                </label>
            </div>

            <SaveButton
                onClick={async () => {
                    const refresh = guiSettings?.dev_mode !== triblerService.getGuiSettings().dev_mode;
                    if (guiSettings)
                        triblerService.setGuiSettings(guiSettings);
                    if (settings)
                        await triblerService.setSettings(settings);
                    if (refresh)
                        window.location.reload();
                }}
            />
        </div>
    )
}
