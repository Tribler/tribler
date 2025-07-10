import {useEffect, useState} from "react";
import {useTranslation} from "react-i18next";
import toast from "react-hot-toast";
import {Torrent} from "@/models/torrent.model";
import {Tooltip, TooltipContent, TooltipProvider, TooltipTrigger} from "./ui/tooltip";
import {formatTimeRelative} from "@/lib/utils";
import {triblerService} from "@/services/tribler.service";
import {isErrorDict} from "@/services/reporting";
import {Icons} from "./icons";

export function SwarmHealth({torrent}: {torrent: Torrent}) {
    const {t} = useTranslation();
    const [checking, setChecking] = useState<boolean>(false);

    useEffect(() => {
        setChecking(false);
    }, [torrent]);

    const bgColor = (t: Torrent) => {
        return t.last_tracker_check === 0
            ? `bg-gray-400`
            : t.num_seeders > 0
              ? `bg-green-400`
              : t.num_leechers > 0
                ? `bg-yellow-400`
                : `bg-red-500`;
    };

    return (
        <TooltipProvider>
            <Tooltip>
                <TooltipTrigger>
                    <div
                        className="flex flex-nowrap items-center whitespace-nowrap cursor-button"
                        onClick={() => {
                            setChecking(true);
                            triblerService.getTorrentHealth(torrent.infohash).then((response) => {
                                if (response === undefined) {
                                    setChecking(false);
                                    toast.error(`${t("ToastErrorDownloadCheck")} ${t("ToastErrorGenNetworkErr")}`);
                                } else if (isErrorDict(response)) {
                                    setChecking(false);
                                    toast.error(`${t("ToastErrorDownloadCheck")} ${response.error.message}`);
                                }
                            });
                        }}>
                        {checking ? (
                            <Icons.spinner className="mr-2" />
                        ) : (
                            <div className={`w-3 h-3 ${bgColor(torrent)} rounded-full mr-2`} />
                        )}
                        <span>
                            S{torrent.num_seeders} L{torrent.num_leechers}
                        </span>
                    </div>
                </TooltipTrigger>
                <TooltipContent>
                    <span>
                        {torrent.last_tracker_check === 0
                            ? "Not checked"
                            : `Checked ${formatTimeRelative(torrent.last_tracker_check)}`}
                    </span>
                </TooltipContent>
            </Tooltip>
        </TooltipProvider>
    );
}
