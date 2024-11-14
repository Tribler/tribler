import SimpleTable from "@/components/ui/simple-table";
import { useEffect, useState } from "react";
import toast from 'react-hot-toast';
import { Dialog, DialogClose, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { DialogProps } from "@radix-ui/react-dialog";
import { JSX } from "react/jsx-runtime";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { ColumnDef } from "@tanstack/react-table";
import { Textarea } from "@/components/ui/textarea";
import { useTranslation } from "react-i18next";
import { triblerService } from "@/services/tribler.service";
import { ErrorDict, isErrorDict } from "@/services/reporting";
import SelectRemotePath from "./SelectRemotePath";
import { PathInput } from "@/components/path-input";
import { Settings } from "@/models/settings.model";


interface Filename {
    path: string;
}

const filenameColumns: ColumnDef<Filename>[] = [
    {
        accessorKey: "path",
        header: "Filename",
        cell: ({ row }) => {
            return <span className="break-all line-clamp-1 text-xs">{row.original.path}</span>
        },
    },
]

export default function CreateTorrent(props: JSX.IntrinsicAttributes & DialogProps) {
    const [name, setName] = useState<string>("");
    const [description, setDescription] = useState<string>("");
    const [destination, setDestination] = useState<string>("");
    const [seed, setSeed] = useState<boolean>(false);

    const [openFileDialog, setOpenFileDialog] = useState<boolean>(false);
    const [openDirDialog, setOpenDirDialog] = useState<boolean>(false);
    const [files, setFiles] = useState<Filename[]>([]);

    const { t } = useTranslation();

    useEffect(() => {

        if (props.open) {
            resetPath();
            setFiles([]);
        }
    }, [props.open]);

    async function resetPath() {
        const settings = await triblerService.getSettings();
        if (settings === undefined){
            toast.error(`${t("ToastErrorDefaultDLDir")} ${t("ToastErrorGenNetworkErr")}`);
        } else if (isErrorDict(settings)) {
            toast.error(`${t("ToastErrorDefaultDLDir")} ${settings.error.message}`);
        } else {
            setDestination(settings.libtorrent.download_defaults.saveas);
        }
    }

    async function addDir(dirname: string) {
        const response = await triblerService.listFiles(dirname, true);
        if (response === undefined){
            toast.error(`${t("ToastErrorDirectoryAdd")} ${t("ToastErrorGenNetworkErr")}`);
        } else if (isErrorDict(response)) {
            toast.error(`${t("ToastErrorDirectoryAdd")} ${response.error.message}`);
        } else {
            setFiles([
                ...files,
                ...response.paths.filter((item) => !item.dir)
            ]);
        }
    }

    async function addFile(filename: string) {
        setFiles([
            ...files,
            { path: filename }
        ]);
    }

    return (
        <Dialog {...props}>
            <DialogContent className="sm:max-w-6xl">
                <DialogHeader>
                    <DialogTitle>Create a new torrent</DialogTitle>
                </DialogHeader>

                <div className="flex flex-col gap-4">
                    <Label htmlFor="name" className="whitespace-nowrap pr-5 pt-2">
                        Name
                    </Label>
                    <Input
                        id="name"
                        className="col-span-2"
                        value={name}
                        onChange={(event) => setName(event.target.value)}
                    />

                    <Label htmlFor="description" className="whitespace-nowrap pr-5 pt-2">
                        Description
                    </Label>
                    <Textarea
                        id="description"
                        className="col-span-2"
                        value={description}
                        onChange={(event) => setDescription(event.target.value)}
                    />

                    <Label htmlFor="files" className="whitespace-nowrap pr-5 pt-2">
                        Files
                    </Label>

                    <SimpleTable
                        data={files}
                        columns={filenameColumns}
                        allowSelect={false}
                        maxHeight={200} />

                    <div>
                        <SelectRemotePath
                            initialPath={destination}
                            selectDir={true}
                            open={openDirDialog}
                            onOpenChange={setOpenDirDialog}
                            onSelect={addDir}
                        />
                        <SelectRemotePath
                            initialPath={destination}
                            selectDir={false}
                            open={openFileDialog}
                            onOpenChange={setOpenFileDialog}
                            onSelect={addFile}
                        />
                        <Button variant="outline" type="button" onClick={() => setOpenDirDialog(true)}>
                            Add directory
                        </Button>
                        <Button variant="outline" type="button" onClick={() => setOpenFileDialog(true)}>
                            Add files
                        </Button>
                    </div>

                    <Label htmlFor="destination" className="whitespace-nowrap pr-5 pt-2">
                        Torrent file destination
                    </Label>
                    <PathInput
                        path={destination}
                        onPathChange={setDestination}
                    />

                    <div className="flex items-center space-x-2 pt-2">
                        <Checkbox
                            id="seed"
                            checked={seed}
                            onCheckedChange={(value) => setSeed(!!value)}
                        />
                        <label
                            htmlFor="seed"
                            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 text-left"
                        >
                            Seed this torrent after creation
                        </label>
                    </div>

                </div>

                <DialogFooter>
                    <Button
                        variant="outline"
                        type="submit"
                        onClick={() => {
                            triblerService.createTorrent(name, description, files.map((f) => f.path), destination, seed).then(
                                (response) => {
                                    if (response === undefined) {
                                        toast.error(`${t("ToastErrorCreateTorrent", {name: name})} ${t("ToastErrorGenNetworkErr")}`);
                                    } else if (isErrorDict(response)) {
                                        // Quinten: according to the typing, response could not be a ErrorDict here?!
                                        toast.error(`${t("ToastErrorCreateTorrent", {name: name})} ${(response as ErrorDict).error.message}`);
                                    }
                                }
                            );
                            if (props.onOpenChange)
                                props.onOpenChange(false);
                        }}
                        disabled={files.length === 0}
                    >
                        {t('CreateTorrentButton')}
                    </Button>
                    <DialogClose asChild>
                        <Button variant="outline" type="button">
                            {t('Cancel')}
                        </Button>
                    </DialogClose>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}
