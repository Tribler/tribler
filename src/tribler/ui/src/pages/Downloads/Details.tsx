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
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Download } from "@/models/download.model";
import Pieces from "./Pieces";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { InfoIcon } from "lucide-react";


export default function DownloadDetails({ selectedDownloads }: { selectedDownloads: Download[] }) {
    const [download, setDownload] = useState<Download | undefined>();
    const tabsRef = useRef<HTMLTableElement>(null);
    const [contentStyle, setContentStyle] = useState<{ height?: string }>({});

    useEffect(() => {
        setDownload((selectedDownloads.length == 1) ? selectedDownloads[0] : undefined);
    }, [selectedDownloads]);

    const { t } = useTranslation();


    useLayoutEffect(() => {
        if (tabsRef.current && contentStyle?.height !== (tabsRef.current.offsetHeight - 40 + "px")) {
            setContentStyle({
                // The 40px (CSS class h-10) is to compensate for the height of the TabsList
                height: tabsRef.current.offsetHeight - 40 + "px",
            })
        }
    });

    if (!download)
        return null;

    return (
        <Tabs ref={tabsRef} defaultValue="details" className="w-full" >
            <TabsList className="flex flex-1 flex-cols-4 border-b">
                <TabsTrigger value="details">{t('Details')}</TabsTrigger>
                <TabsTrigger value="files">{t('Files')}</TabsTrigger>
                <TabsTrigger value="trackers">{t('Trackers')}</TabsTrigger>
                <TabsTrigger value="peers">{t('Peers')}</TabsTrigger>
            </TabsList>

            <TabsContent value="details" style={contentStyle}>
                <ScrollArea className="h-full">
                    <div className="flex flex-col p-4 text-sm">
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Progress')}</div>
                            <div className="basis-3/4 m-auto"><Pieces numpieces={download.total_pieces} pieces64={download.pieces || ''} /></div>
                        </div>
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Name')}</div>
                            <div className="basis-3/4 break-all line-clamp-1">{download.name}</div>
                        </div>
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Status')}</div>
                            <div className="basis-3/4">{capitalize(download.status)}</div>
                        </div>
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Filesize')}</div>
                            <div className="basis-3/4">{formatBytes(download.size)}</div>
                        </div>
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Health')}</div>
                            <div className="basis-3/4">{t('SeedersLeechers', { seeders: download.num_seeds, leechers: download.num_peers })}</div>
                        </div>
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Infohash')}</div>
                            <div className="basis-3/4">{download.infohash}</div>
                        </div>
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Destination')}</div>
                            <div className="basis-3/4 break-all line-clamp-1 flex flex-nowrap items-center">
                                {download.destination}
                                {download.completed_dir && download.completed_dir !== download.destination && (
                                    <TooltipProvider>
                                        <Tooltip>
                                            <TooltipTrigger>
                                                <InfoIcon className="w-4 ml-2"/>
                                            </TooltipTrigger>
                                            <TooltipContent>
                                                <span>
                                                    {t('MoveAfterCompletionInfo')} <div className="font-semibold">{download.completed_dir}</div>
                                                </span>
                                            </TooltipContent>
                                        </Tooltip>
                                    </TooltipProvider>
                                )}
                            </div>
                        </div>
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Ratio')}</div>
                            <div className="basis-3/4">{
                                download.all_time_ratio < 0 ?
                                    String(`∞`) :
                                    download.all_time_ratio.toFixed(2)}
                                &nbsp;({formatBytes(download.all_time_upload)} / {formatBytes(download.size * download.progress)})
                            </div>
                        </div>
                        <div className="flex flex-row">
                            <div className="basis-1/4">{t('Availability')}</div>
                            <div className="basis-3/4">{download.availability}</div>
                        </div>
                    </div>
                </ScrollArea>
            </TabsContent>
            <TabsContent value="files" style={contentStyle}>
                <ScrollArea className="h-full">
                    <Files download={download} key={download.infohash} />
                </ScrollArea>
            </TabsContent>
            <TabsContent value="trackers" style={contentStyle}>
                <ScrollArea className="h-full">
                    <Trackers download={download} />
                </ScrollArea>
            </TabsContent>
            <TabsContent value="peers" style={contentStyle}>
                <ScrollArea className="h-full">
                    <Peers download={download} height={contentStyle.height} />
                </ScrollArea>
            </TabsContent>
        </Tabs>
    )
}
