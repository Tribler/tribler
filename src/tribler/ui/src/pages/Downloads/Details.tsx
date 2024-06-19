import { capitalize, formatBytes } from "@/lib/utils";
import {
    Tabs,
    TabsContent,
    TabsList,
    TabsTrigger,
} from "@/components/ui/tabs"
import Files from "./Files";
import Peers from "./Peers";
import Trackers from "./Trackers";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Download } from "@/models/download.model";
import Pieces from "./Pieces";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";


export default function DownloadDetails({ selectedDownloads }: { selectedDownloads: Download[] }) {
    const [download, setDownload] = useState<Download | undefined>();

    useEffect(() => {
        setDownload((selectedDownloads.length == 1) ? selectedDownloads[0] : undefined);
    }, [selectedDownloads]);

    const { t } = useTranslation();

    if (!download)
        return null;

    return (
        <ScrollArea className="w-full">
            <Tabs defaultValue="details" className="w-full flex flex-col flex-wrap">
                <TabsList className="flex-1 flex-cols-4">
                    <TabsTrigger value="details">{t('Details')}</TabsTrigger>
                    <TabsTrigger value="files">{t('Files')}</TabsTrigger>
                    <TabsTrigger value="trackers">{t('Trackers')}</TabsTrigger>
                    <TabsTrigger value="peers">{t('Peers')}</TabsTrigger>
                </TabsList>
                <TabsContent value="details" >
                    <div className="flex flex-col h-full p-4 text-sm">
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Progress')}</div>
                            <div className="basis-3/4 m-auto"><Pieces pieces64={download.pieces || ''} /></div>
                        </div>
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Name')}</div>
                            <div className="basis-3/4">{download?.name}</div>
                        </div>
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Status')}</div>
                            <div className="basis-3/4">{capitalize(download?.status)}</div>
                        </div>
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Filesize')}</div>
                            <div className="basis-3/4">{formatBytes(download?.size)}</div>
                        </div>
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Health')}</div>
                            <div className="basis-3/4">{t('SeedersLeechers', { seeders: download?.num_seeds, leechers: download?.num_peers })}</div>
                        </div>
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Infohash')}</div>
                            <div className="basis-3/4">{download?.infohash}</div>
                        </div>
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Destination')}</div>
                            <div className="basis-3/4">{download?.destination}</div>
                        </div>
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Ratio')}</div>
                            <div className="basis-3/4">{download?.all_time_ratio.toFixed(2)} ({formatBytes(download?.all_time_upload)} upload; {formatBytes(download?.all_time_download)} dowload)</div>
                        </div>
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Availability')}</div>
                            <div className="basis-3/4">{download?.availability}</div>
                        </div>
                    </div>
                </TabsContent>
                <TabsContent value="files">
                    <Files download={download} key={download.infohash} />
                </TabsContent>
                <TabsContent value="trackers">
                    <Trackers download={download} />
                </TabsContent>
                <TabsContent value="peers">
                    <Peers download={download} />
                </TabsContent>
            </Tabs>
        </ScrollArea>
    )
}
