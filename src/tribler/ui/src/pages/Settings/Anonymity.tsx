import SaveButton from "./SaveButton";
import toast from 'react-hot-toast';
import { Slider } from "@/components/ui/slider";
import { Settings } from "@/models/settings.model";
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
import { useState } from "react";
import { useTranslation } from "react-i18next";


export default function Anonimity() {
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

    function hopsToString(hops: number | undefined) {
        switch(hops){
            case 3: {return t("ThreeHops");}
            case 2: {return t("TwoHops");}
            default: {return t("OneHop");}
        }
    }

    return (
        <div className="p-6 w-full max-w-[700px]">
            <p>{t('HopInfo')}</p>
            <br />
            <p>{t('ForMoreInfoRead')} <a href="https://www.tribler.org/anonymity.html" className="font-semibold">https://www.tribler.org/anonymity.html</a>.</p>
            <br />
            <div className="flex items-center py-4">
                <div className="whitespace-pre-line text-xs text-center px-2">
                    {t('MinHops')}
                </div>
                <Slider
                    value={[settings?.libtorrent?.download_defaults?.number_hops ?? 1]}
                    min={1}
                    max={3}
                    step={1}
                    onValueChange={(value) => {
                        if (settings) {
                            setSettings({
                                ...settings,
                                libtorrent: {
                                    ...settings.libtorrent,
                                    download_defaults: {
                                        ...settings.libtorrent.download_defaults,
                                        number_hops: value[0]
                                    }
                                }
                            });
                        }
                    }}
                />
                <div className="whitespace-pre text-xs text-center px-2">
                    {t('MaxHops')}
                </div>
            </div>
            <div className="flex justify-center w-full"><span className="text-xl text-muted-foreground font-bold">{hopsToString(settings?.libtorrent?.download_defaults?.number_hops)}</span></div>
            <br />
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
