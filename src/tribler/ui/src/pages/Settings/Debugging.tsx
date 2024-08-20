import { Checkbox } from "@/components/ui/checkbox";
import { Settings } from "@/models/settings.model";
import { triblerService } from "@/services/tribler.service";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import SaveButton from "./SaveButton";


export default function Debugging() {
    const { t } = useTranslation();
    const [settings, setSettings] = useState<Settings>();

    if (!settings) {
        (async () => { setSettings(await triblerService.getSettings()) })();
        return;
    }

    return (
        <div className="p-6">
            <div className="flex items-center space-x-2 p-2">
                <Checkbox
                    checked={settings?.ui?.dev_mode === true}
                    onCheckedChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                ui: {
                                    ...settings.ui,
                                    dev_mode: !!value
                                }
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
                    if (settings)
                        await triblerService.setSettings(settings);
                        window.location.reload();
                }}
            />
        </div>
    )
}
