import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Settings } from "@/models/settings.model";
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import toast from 'react-hot-toast';
import SaveButton from "./SaveButton";


export default function Bandwith() {
    const { t } = useTranslation();
    const [settings, setSettings] = useState<Settings>();

    if (!settings) {
        (async () => {
            const response = await triblerService.getSettings();
            if (response === undefined) {
                toast.error(`${t("ToastErrorGetSettings")} ${t("ToastErrorGenNetworkErr")}`);
            } else if (isErrorDict(response)){
                toast.error(`${t("ToastErrorGetSettings")} ${response.error.message}`);
            } else {
                setSettings(response);
            }
        })();
        return null;
    }

    return (
        <div className="p-6">
            <div className="grid grid-cols-3 gap-2 items-center">
                <Label htmlFor="max_upload_rate" className="whitespace-nowrap pr-5">
                    {t('UploadRate')}
                </Label>
                <Input
                    type="number"
                    id="max_upload_rate"
                    value={settings && settings?.libtorrent?.max_upload_rate / 1024}
                    onChange={(event) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    max_upload_rate: Math.max(0, +event.target.value) * 1024
                                }
                            });
                        }
                    }}
                />
                <Label htmlFor="max_upload_rate" className="whitespace-nowrap pr-5">
                    {t('RateUnit')}
                </Label>

                <Label htmlFor="max_download_rate" className="whitespace-nowrap pr-5">
                    {t('DownloadRate')}
                </Label>
                <Input
                    type="number"
                    id="max_download_rate"
                    value={settings && settings?.libtorrent?.max_download_rate / 1024}
                    onChange={(event) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    max_download_rate: Math.max(0, +event.target.value) * 1024
                                }
                            });
                        }
                    }}
                />
                <Label htmlFor="max_download_rate" className="whitespace-nowrap pr-5">
                    {t('RateUnit')}
                </Label>
            </div>
            <p className="text-xs pt-2 pb-4 text-muted-foreground">{t('RateLimitNote')}</p>

            <SaveButton
                onClick={async () => {
                    if (settings){
                        const response = await triblerService.setSettings(settings);
                        if (response === undefined) {
                            toast.error(`${t("ToastErrorSetSettings")} ${t("ToastErrorGenNetworkErr")}`);
                        } else if (isErrorDict(response)){
                            toast.error(`${t("ToastErrorSetSettings")} ${response.error.message}`);
                        }
                    }
                }}
            />
        </div>
    )
}
