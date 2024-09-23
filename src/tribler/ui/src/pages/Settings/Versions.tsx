import { Suspense, useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
import { useInterval } from "@/hooks/useInterval";
import { useTranslation } from "react-i18next";
import { RefreshCw } from 'lucide-react';

export default function Versions() {
    const { t } = useTranslation();

    const initStateRef = useRef<number>(0);
    const [version, setVersion] = useState<string | undefined>();
    const [versions, setVersions] = useState<string[]>(new Array());
    const [newVersion, setNewVersion] = useState<boolean>(false);
    const [canUpgrade, setCanUpgrade] = useState<boolean>(false);
    const [isUpgrading, setIsUpgrading] = useState<boolean>(false);

    const clickedImport = (e: React.MouseEvent<HTMLElement>, old_version: string) => {
        setIsUpgrading(true);
        triblerService.performUpgrade().then((response) => {
            if (response === undefined) {
                toast.error(`${t("ToastErrorUpgradeFailed")} ${t("ToastErrorGenNetworkErr")}`);
                setIsUpgrading(false);
            } else if (isErrorDict(response)){
                toast.error(`${t("ToastErrorUpgradeFailed")} ${response.error}`);
                setIsUpgrading(false);
            }
        });
    }

    const clickedRemove = (e: React.MouseEvent<HTMLElement>, old_version: string) => {
        triblerService.removeVersion(old_version).then((response) => {
            if (response === undefined) {
                toast.error(`${t("ToastErrorRemoveVersion", {version: old_version})} ${t("ToastErrorGenNetworkErr")}`);
            } else if (isErrorDict(response)){
                toast.error(`${t("ToastErrorRemoveVersion", {version: old_version})}  ${response.error}`);
            } else {
                setVersions(versions.filter((v) => v != old_version));
            }
        });
    }

    const initVersionInfo = (async () => {
        switch(initStateRef.current){
            case 0: {
                const version = await triblerService.getVersion();
                if (!(version === undefined) && !isErrorDict(version)) {
                    setVersion(version);
                    initStateRef.current = 1;
                } else {
                    break;  // Don't bother the user on error, just initialize later.
                }
            }
            case 1: {
                var allVersions = await triblerService.getVersions();
                if (!(allVersions === undefined) && !isErrorDict(allVersions)) {
                    const current_version = allVersions.current;
                    const versions = (allVersions.versions).filter((v: string) => v != current_version);
                    setVersions(versions);
                    initStateRef.current = 2;
                } else {
                    break;  // Don't bother the user on error, just initialize later.
                }
            }
            case 2: {
                const canUpgrade = await triblerService.canUpgrade();
                if (!(canUpgrade === undefined) && !isErrorDict(canUpgrade)) {
                    setCanUpgrade(canUpgrade);
                    initStateRef.current = 3;
                } else {
                    break;  // Don't bother the user on error, just initialize later.
                }
            }
            default: {
                break;
            }
        }
    });

    useEffect(() => {
        initVersionInfo();
    }, []);
    useInterval(() => {
        if (initStateRef.current < 3) {
            initVersionInfo();
        }

        triblerService.isUpgrading().then((isUpgrading) => {
            if (isUpgrading !== undefined && !isErrorDict(isUpgrading)) {
                // Don't bother the user on error, just try again later.
                setIsUpgrading(isUpgrading);
            }
        });

        triblerService.getNewVersion().then((newVersion) => {
            if (newVersion !== undefined && !isErrorDict(newVersion)) {
                // Don't bother the user on error, just try again later.
                setNewVersion(newVersion);
            }
        });
    }, 5000);

    return (
        <div className="p-6">
            <div className="grid grid-cols-4 gap-2 items-center">
                <Label className="whitespace-nowrap pr-5 font-bold">
                    {t('VersionCurrent')}:
                </Label>
                <Suspense fallback={<Label>...</Label>}>
                    <Label>
                        {version ? version : "..."}
                    </Label>
                </Suspense>
                <Suspense fallback={<Label></Label>}>
                    {newVersion ? <Label>{t('VersionAvailable')}: {newVersion}</Label> : <Label></Label>}
                </Suspense>
                <Label></Label>

                <Label style={{marginBottom: "1cm"}}></Label>
                <Label></Label><Label></Label><Label></Label>

                <Label className="whitespace-nowrap pr-5 font-bold">{t('VersionOld')}</Label>
                <Label></Label><Label></Label><Label></Label>

                {
                    versions.reduce((r: string[], e: string) => {r.push(e, e, e, e); return r;}, new Array<string>()).map(function(old_version: string, i: number){
                        switch (i % 4){
                            case 0: {
                                return (<Label>{old_version}</Label>)
                            }
                            case 1: {
                                return (<Label></Label>)  // Blank column to outline with the data above
                            }
                            case 2: {
                                return (
                                           (typeof canUpgrade === "string") && (canUpgrade == old_version) ? (
                                               isUpgrading ? <div className="flex justify-center p-5 gap-1"><RefreshCw opacity="0.5" className="animate-spin duration-500" /><Label className="content-center text-muted-foreground">{t('VersionUpgrading')}...</Label></div>
                                               : <Button variant="default" type="submit" onClick={(e) => clickedImport(e, old_version)}>{t('VersionImport')}</Button>)
                                           : <Label></Label>
                                       )
                            }
                            default: {
                                return (<Button variant="destructive" type="submit" onClick={(e) => clickedRemove(e, old_version)}>{t('VersionRemove')}</Button>)
                            }
                        }
                    })
                }
            </div>
        </div>
    )
}
