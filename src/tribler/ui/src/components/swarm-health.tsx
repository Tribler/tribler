import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from 'react-hot-toast';
import { Torrent } from "@/models/torrent.model";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./ui/tooltip";
import { formatTimeRelative } from "@/lib/utils";
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";


export function SwarmHealth({ torrent }: { torrent: Torrent }) {
    const { t } = useTranslation();
    const [checking, setChecking] = useState<boolean>(false)

    useEffect(() => {
        setChecking(false);
    }, [torrent]);

    const bgColor = (t: Torrent) => {
        return t.last_tracker_check === 0 ?
            `bg-gray-400` : (t.num_seeders > 0 ?
                `bg-green-400` : (t.num_leechers > 0 ?
                    `bg-yellow-400` : `bg-red-500`))
    }

    return (
        <TooltipProvider>
            <Tooltip>
                <TooltipTrigger>
                    <div
                        className="flex flex-nowrap items-center whitespace-nowrap cursor-button"
                        onClick={() => {
                            setChecking(true);
                            triblerService.getTorrentHealth(torrent.infohash).then((response) => {
                                if (response === undefined){
                                    setChecking(false);
                                    toast.error(`${t("ToastErrorDownloadCheck")} ${t("ToastErrorGenNetworkErr")}`);
                                } else if (isErrorDict(response)) {
                                    setChecking(false);
                                    toast.error(`${t("ToastErrorDownloadCheck")} ${response.error.message}`);
                                }
                            });
                        }}
                    >
                        {checking ?
                            <svg className="animate-spin h-3 w-3 text-black dark:text-white mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            :
                            <div className={`w-3 h-3 ${bgColor(torrent)} rounded-full mr-2`} />
                        }
                        <span>S{torrent.num_seeders} L{torrent.num_leechers}</span>
                    </div>
                </TooltipTrigger>
                <TooltipContent>
                    <span>
                        {torrent.last_tracker_check === 0 ? 'Not checked' : `Checked ${formatTimeRelative(torrent.last_tracker_check)}`}
                    </span>
                </TooltipContent>
            </Tooltip>
        </TooltipProvider>
    )
}
