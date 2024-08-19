import { Suspense, useEffect, useState } from 'react';
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { triblerService } from "@/services/tribler.service";
import { useTranslation } from "react-i18next";
import { RefreshCw } from 'lucide-react';

export default function Versions() {
    const { t } = useTranslation();

    const [version, setVersion] = useState();
    const [versions, setVersions] = useState(new Array());
    const [newVersion, setNewVersion] = useState(false);
    const [canUpgrade, setCanUpgrade] = useState(false);
    const [isUpgrading, setIsUpgrading] = useState(false);

    const clickedImport = (e, old_version?) => {
        triblerService.performUpgrade();
        setIsUpgrading(true);
    }

    const clickedRemove = (e, old_version?) => {
        triblerService.removeVersion(old_version);
        setVersions(versions.filter((v) => v != old_version));
    }

    const useMountEffect = (fun) => useEffect(fun, [])
    useMountEffect(() => {
        (async () => {
            const version = await triblerService.getVersion();
            setVersion(version);

            var allVersions = await triblerService.getVersions();
            const versions = (allVersions.versions).filter((v) => v != allVersions.current);
            setVersions(versions);

            const newVersion = await triblerService.getNewVersion();
            setNewVersion(newVersion);

            const canUpgrade = await triblerService.canUpgrade();
            setCanUpgrade(canUpgrade);
        })();
    });
    useEffect(() => {
        (async () => {
            const isUpgrading = await triblerService.isUpgrading();
            setIsUpgrading(isUpgrading)
        })();
    });

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
                    versions.reduce((r, e) => r.push(e, e, e, e) && r, []).map(function(old_version, i){
                        switch (i % 4){
                            case 0: {
                                return (<Label>{old_version}</Label>)
                            }
                            case 1: {
                                return (<Label></Label>)  // Blank column to outline with the data above
                            }
                            case 2: {
                                return (
                                           canUpgrade == old_version ? (
                                               isUpgrading ? <div className="flex justify-center p-5 gap-1"><RefreshCw opacity="0.5" class="animate-spin duration-500" /><Label className="content-center text-muted-foreground">{t('VersionUpgrading')}...</Label></div>
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
