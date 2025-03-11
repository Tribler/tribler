import { useState } from "react";
import toast from 'react-hot-toast';
import SimpleTable, { getHeader } from "@/components/ui/simple-table";
import { Dialog, DialogClose, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Download } from "@/models/download.model";
import { Tracker } from "@/models/tracker.model";
import { ColumnDef } from "@tanstack/react-table";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { triblerService } from "@/services/tribler.service";
import { isErrorDict } from "@/services/reporting";
import { useTranslation } from "react-i18next";


interface TrackerRow extends Tracker {
    recheckButton: typeof Button;
    removeButton: typeof Button;
}

export default function Trackers({ download }: { download: Download }) {
    const { t } = useTranslation();

    const [trackerDialogOpen, setTrackerDialogOpen] = useState<boolean>(false);
    const [trackerInput, setTrackerInput] = useState('');

    const trackerColumns: ColumnDef<TrackerRow>[] = [
        {
            accessorKey: "url",
            header: getHeader('Name'),
        },
        {
            accessorKey: "status",
            header: getHeader('Status'),
        },
        {
            accessorKey: "peers",
            header: getHeader('Peers'),
        },
        {
            header: "",
            accessorKey: "recheckButton",
            cell: (props) => {
                    return (["[DHT]", "[PeX]"].includes(props.row.original.url) ? <></> :
                        <Button variant="secondary" className="max-h-6" onClick={(event) => {
                            triblerService.forceCheckDownloadTracker(download.infohash, props.row.original.url).then((response) => {
                                if (response === undefined) {
                                    toast.error(`${"ToastErrorTrackerCheck"} ${"ToastErrorGenNetworkErr"}`);
                                } else if (isErrorDict(response)){
                                    toast.error(`${"ToastErrorTrackerCheck"} ${response.error.message}`);
                                }
                            });
                        }}>{t("ForceRecheck")}</Button>)
            }
        },
        {
            header: "",
            accessorKey: "removeButton",
            cell: (props) => {
                    return (["[DHT]", "[PeX]"].includes(props.row.original.url) ? <></> :
                        <Button variant="secondary" className="max-h-6" onClick={(event) => {
                            triblerService.removeDownloadTracker(download.infohash, props.row.original.url).then((response) => {
                                if (response === undefined) {
                                    toast.error(`${"ToastErrorTrackerRemove"} ${"ToastErrorGenNetworkErr"}`);
                                } else if (isErrorDict(response)){
                                    toast.error(`${"ToastErrorTrackerRemove"} ${response.error.message}`);
                                } else {
                                    download.trackers = download.trackers.filter(tracker => {return tracker.url != props.row.original.url});
                                    var button = event.target as HTMLButtonElement;
                                    button.disabled = true;
                                    button.classList.add("cursor-not-allowed");
                                    button.classList.add("opacity-50");
                                }
                            });
                        }}>❌</Button>)
            }
        }
    ]

    if (download.trackers.length === 0)
        return <svg className="animate-spin h-3 w-3 text-black dark:text-white ml-4 mt-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                   <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                   <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
               </svg>;

    return (
        <div>
            <div className="border-b-4 border-muted">
                <SimpleTable data={download.trackers as TrackerRow[]} columns={trackerColumns} maxHeight={''} />
            </div>
            <Button className="mx-4 my-2 min-w-24 max-h-8" variant="secondary" onClick={() => { setTrackerDialogOpen(true) }}>{t('Add')}</Button>

            <Dialog open={trackerDialogOpen} onOpenChange={setTrackerDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{t('TrackerDialogHeader')}</DialogTitle>
                    </DialogHeader>
                    <div className="grid gap-1 py-4 text-sm">
                        {t('TrackerDialogInputLabel')}
                        <div className="grid grid-cols-6 items-center gap-4">
                            <Input
                                id="uri"
                                className="col-span-5 pt-0"
                                value={trackerInput}
                                onChange={(event) => setTrackerInput(event.target.value)}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            type="submit"
                            onClick={() => {
                                if (trackerInput) {
                                    triblerService.addDownloadTracker(download.infohash, trackerInput).then((response) => {
                                        if (response === undefined) {
                                            toast.error(`${"ToastErrorTrackerAdd"} ${"ToastErrorGenNetworkErr"}`);
                                        } else if (isErrorDict(response)) {
                                            toast.error(`${"ToastErrorTrackerAdd"} ${response.error.message}`);
                                        }
                                    });
                                    setTrackerDialogOpen(false);
                                }
                            }}>
                            {t('Add')}
                        </Button>
                        <DialogClose asChild>
                            <Button variant="outline" type="button">
                                {t('Cancel')}
                            </Button>
                        </DialogClose>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    )
}
