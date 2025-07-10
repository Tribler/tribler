import {useState} from "react";
import toast from "react-hot-toast";
import SimpleTable, {getHeader} from "@/components/ui/simple-table";
import {Dialog, DialogClose, DialogContent, DialogFooter, DialogHeader, DialogTitle} from "@/components/ui/dialog";
import {Download} from "@/models/download.model";
import {Tracker} from "@/models/tracker.model";
import {ColumnDef} from "@tanstack/react-table";
import {Input} from "@/components/ui/input";
import {Button} from "@/components/ui/button";
import {triblerService} from "@/services/tribler.service";
import {isErrorDict} from "@/services/reporting";
import {useTranslation} from "react-i18next";
import {Icons} from "@/components/icons";
import {ContextMenu, ContextMenuContent, ContextMenuItem, ContextMenuTrigger} from "@/components/ui/context-menu";
import {Plus, RefreshCw, Trash} from "lucide-react";

interface TrackerRow extends Tracker {
    recheckButton: typeof Button;
    removeButton: typeof Button;
}

export default function Trackers({download, style}: {download: Download; style?: React.CSSProperties}) {
    const {t} = useTranslation();

    const [trackerDialogOpen, setTrackerDialogOpen] = useState<boolean>(false);
    const [trackerInput, setTrackerInput] = useState("");
    const [selectedTrackers, setSelectedTrackers] = useState<Tracker[]>([]);

    const trackerColumns: ColumnDef<TrackerRow>[] = [
        {
            accessorKey: "url",
            header: getHeader("Name"),
        },
        {
            accessorKey: "status",
            header: getHeader("Status"),
        },
        {
            accessorKey: "peers",
            header: getHeader("Peers"),
            cell: (props) => ((props.row.original?.peers ?? -1) >= 0 ? <>{props.row.original.peers}</> : <></>),
        },
        {
            accessorKey: "seeds",
            header: getHeader("Seeds"),
            cell: (props) => ((props.row.original?.seeds ?? -1) >= 0 ? <>{props.row.original.seeds}</> : <></>),
        },
        {
            accessorKey: "leeches",
            header: getHeader("Leeches"),
            cell: (props) => ((props.row.original?.leeches ?? -1) >= 0 ? <>{props.row.original.leeches}</> : <></>),
        },
    ];

    if (download.trackers.length === 0) return <Icons.spinner className="ml-4 mt-4" />;

    return (
        <>
            <ContextMenu modal={false}>
                <ContextMenuTrigger>
                    <SimpleTable
                        className="border-b-4 border-muted"
                        data={download.trackers as TrackerRow[]}
                        allowSelect={true}
                        selectOnRightClick={true}
                        onSelectedRowsChange={setSelectedTrackers}
                        columns={trackerColumns}
                        style={style}
                    />
                </ContextMenuTrigger>
                <ContextMenuContent className="w-64 bg-neutral-50 dark:bg-neutral-950">
                    <ContextMenuItem
                        className="hover:bg-neutral-200 dark:hover:bg-neutral-800"
                        onClick={() => setTrackerDialogOpen(true)}>
                        <Plus className="w-5 mx-2" />
                        {t("Add")}..
                    </ContextMenuItem>
                    <ContextMenuItem
                        className="hover:bg-neutral-200 dark:hover:bg-neutral-800"
                        disabled={selectedTrackers.length !== 1 || ["[DHT]", "[PeX]"].includes(selectedTrackers[0].url)}
                        onClick={() => {
                            triblerService
                                .removeDownloadTracker(download.infohash, selectedTrackers[0].url)
                                .then((response) => {
                                    if (response === undefined) {
                                        toast.error(`${t("ToastErrorTrackerRemove")} ${t("ToastErrorGenNetworkErr")}`);
                                    } else if (isErrorDict(response)) {
                                        toast.error(`${t("ToastErrorTrackerRemove")} ${response.error.message}`);
                                    }
                                });
                        }}>
                        <Trash className="w-5 mx-2" />
                        {t("Remove")}
                    </ContextMenuItem>
                    <ContextMenuItem
                        className="hover:bg-neutral-200 dark:hover:bg-neutral-800"
                        disabled={selectedTrackers.length !== 1 || ["[DHT]", "[PeX]"].includes(selectedTrackers[0].url)}
                        onClick={() => {
                            triblerService
                                .forceCheckDownloadTracker(download.infohash, selectedTrackers[0].url)
                                .then((response) => {
                                    if (response === undefined) {
                                        toast.error(`${t("ToastErrorTrackerCheck")} ${t("ToastErrorGenNetworkErr")}`);
                                    } else if (isErrorDict(response)) {
                                        toast.error(`${t("ToastErrorTrackerCheck")} ${response.error.message}`);
                                    }
                                });
                        }}>
                        <RefreshCw className="w-5 mx-2" />
                        {t("ForceRecheck")}
                    </ContextMenuItem>
                </ContextMenuContent>
            </ContextMenu>

            <Dialog open={trackerDialogOpen} onOpenChange={setTrackerDialogOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{t("TrackerDialogHeader")}</DialogTitle>
                    </DialogHeader>
                    <div className="grid gap-1 py-4 text-sm">
                        {t("TrackerDialogInputLabel")}
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
                                    triblerService
                                        .addDownloadTracker(download.infohash, trackerInput)
                                        .then((response) => {
                                            if (response === undefined) {
                                                toast.error(
                                                    `${t("ToastErrorTrackerAdd")} ${t("ToastErrorGenNetworkErr")}`
                                                );
                                            } else if (isErrorDict(response)) {
                                                toast.error(`${t("ToastErrorTrackerAdd")} ${response.error.message}`);
                                            }
                                        });
                                    setTrackerDialogOpen(false);
                                }
                            }}>
                            {t("Add")}
                        </Button>
                        <DialogClose asChild>
                            <Button variant="outline" type="button">
                                {t("Cancel")}
                            </Button>
                        </DialogClose>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
