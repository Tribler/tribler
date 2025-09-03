import SimpleTable, {getHeader} from "@/components/ui/simple-table";
import {useEffect, useState} from "react";
import toast from "react-hot-toast";
import {Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle} from "@/components/ui/dialog";
import {Button} from "@/components/ui/button";
import {ScrollArea} from "@/components/ui/scroll-area";
import {DialogProps} from "@radix-ui/react-dialog";
import {JSX} from "react/jsx-runtime";
import {Checkbox} from "@/components/ui/checkbox";
import {Label} from "@/components/ui/label";
import {Input} from "@/components/ui/input";
import {ColumnDef} from "@tanstack/react-table";
import {Textarea} from "@/components/ui/textarea";
import {useTranslation} from "react-i18next";
import {triblerService} from "@/services/tribler.service";
import {ErrorDict, isErrorDict} from "@/services/reporting";
import SelectRemotePath from "./SelectRemotePath";
import {PathInput} from "@/components/path-input";
import {Settings} from "@/models/settings.model";
import {Icons} from "@/components//icons";
import {ArrowDown, ArrowUp, Plus, Trash2} from "lucide-react";

interface Filename {
    selected?: string;
    path: string;
    suggestion: string;
    src: string;
}

enum NameValid {
  Pending = 1,
  Valid,
  Invalid,
}


export default function CreateTorrent(props: JSX.IntrinsicAttributes & DialogProps) {
    const [name, setName] = useState<string>("");
    const [isNameValid, setIsNameValid] = useState<NameValid>(NameValid.Pending);
    const [debounceNameInput, setDebounceNameInput] = useState<[HTMLInputElement | undefined, string]>([undefined, ""]);

    const [description, setDescription] = useState<string>("");
    const [destination, setDestination] = useState<string>("");
    const [trackers, setTrackers] = useState<string>("");
    const [initialNodes, setInitialNodes] = useState<string>("");

    const [openFileDialog, setOpenFileDialog] = useState<boolean>(false);
    const [openDirDialog, setOpenDirDialog] = useState<boolean>(false);
    const [files, setFiles] = useState<Filename[]>([]);
    const [onlyFile, setOnlyFile] = useState<string | undefined>(undefined);
    const [selectedRows, setSelectedRows] = useState<Filename[]>([]);
    const [hasNoSelection, setHasNoSelection] = useState(true);

    const {t} = useTranslation();

    useEffect(() => {
        if (props.open) {
            resetPath();
            setOnlyFile(undefined);
            setFiles([]);
            setSelectedRows([]);
            setHasNoSelection(true);
            setName("");
            setIsNameValid(NameValid.Pending);
            setDescription("");
            setTrackers("");
            setInitialNodes("");
        }
    }, [props.open]);

    function handleFileSubmit(index: number, value: string) {
        let changed = false;
        const newFiles = files.map((c, i) => {
            if (i == index) {
                if (c.src != value) {
                    changed = true;
                    return {path: "", src: value, suggestion: value.replace(/^.*[\\/]/, ""), selected: c.selected};
                }
            }
            return c;
        })
        if (changed)
            setFiles(newFiles);
    }

    const filenameColumns: ColumnDef<Filename>[] = [
        {
            accessorKey: "suggestion",
            header: getHeader("Name"),
            cell: ({row}) => {
                const [value, setValue] = useState(row.original.path);
                const [selected, setSelected] = useState(row.original.selected);
                useEffect(() => {
                    row.original.path = value;
                    let changed = false;
                    const newFiles = files.map((c, i) => {
                        if (("" + i) == row.id) {
                            if (c.path != value) {
                                changed = true;
                                return {...c, path: value};
                            }
                        }
                        return c;
                    })
                    if (changed)
                        setFiles(newFiles);
                }, [value]);
                useEffect(() => {
                    if (selected === undefined) {
                        // Update to switch off, check if we already knew about this update.
                        let changed = false;
                        const newlySelected = selectedRows.filter((e, i, a) => {
                            if (e.selected == row.id){
                                changed = true;
                                return false;
                            } else {
                                return true;
                            }
                        });
                        if (changed) {
                            row.original.selected = selected;
                            setSelectedRows(newlySelected);
                            setHasNoSelection(newlySelected.length == 0);
                        }
                    } else {
                        // Update to switch on, check if we already knew about this update.
                        if (selectedRows.find((element) => element.selected == row.id) === undefined){
                            row.original.selected = selected;
                            let changed = false;
                            const newlySelected = selectedRows.map((c, i) => {
                                if (("" + i) == row.id) {
                                    changed = true;
                                    return {...c, selected: row.id};
                                }
                                return c;
                            })
                            if (!changed)
                                newlySelected.push({...row.original, selected: row.id});
                            setSelectedRows(newlySelected);
                            setHasNoSelection(false);
                        }
                    }
                }, [selected]);
                return (
                        <form className="flex flex-row items-center">
                            <Checkbox className="mr-2" checked={selected !== undefined} onCheckedChange={(e) => {setSelected(e ? row.id : undefined);}} />
                            <Input list="placeholders" disabled={row.original.src === ""}
                                placeholder={row.original.suggestion}
                                value={value}
                                onChange={e => setValue(e.target.value)} />
                            <datalist id="placeholders">
                                <option value={row.original.suggestion} />
                            </datalist>
                        </form>
                        );
            },
        },
        {
            accessorKey: "src",
            header: getHeader("Files"),
            cell: ({ getValue, row: { index }, column: { id }, table }) => {
                const initialValue = getValue<string>();
                const [value, setValue] = useState<string>(initialValue);
                useEffect(() => {
                    handleFileSubmit(index, value);
                }, [value]);
                useEffect(() => {
                    setValue(initialValue);
                }, [initialValue]);
                return (<PathInput directory={false} path={value}
                            onPathChange={(userValue) => {setValue(userValue);}} />);
            },
        },
    ];

    async function resetPath() {
        const settings = await triblerService.getSettings();
        if (settings === undefined) {
            toast.error(`${t("ToastErrorDefaultDLDir")} ${t("ToastErrorGenNetworkErr")}`);
        } else if (isErrorDict(settings)) {
            toast.error(`${t("ToastErrorDefaultDLDir")} ${settings.error.message}`);
        } else {
            setDestination(settings.libtorrent.download_defaults.saveas);
        }
    }

    async function addFile() {
        setFiles([...files, {path: "", src: "", suggestion: "", selected: undefined}]);
    }

    function setInvalidName(target: HTMLInputElement){
        setIsNameValid(NameValid.Invalid);
        target.style.borderColor = "#c96155";
    }

    function setValidName(target: HTMLInputElement){
        setIsNameValid(NameValid.Valid);
        target.style.borderColor = "#62c955";
    }

    function setPending(target: HTMLInputElement){
        setIsNameValid(NameValid.Pending);
        target.style.borderColor = "";
    }

    async function requestNameValidity(target: HTMLInputElement) {
        let name = target.value;
        if (name == "") {
            setInvalidName(target);
            return
        } else {
            setPending(target);
        }

        const response = await triblerService.dryCreateTorrent(name, destination);
        if (response === undefined) {
            setInvalidName(target);
        } else if (isErrorDict(response)) {
            setInvalidName(target);
        } else {
            if (response) {
                setValidName(target);
            } else {
                setInvalidName(target);
            }
        }
    }

    function removeSelected() {
        const selectedRowIds = selectedRows.map((c, i) => {return c.selected;});
        const newFiles = files.filter((e, i, a) => {
            return !selectedRowIds.includes(e.selected);
        }).map((c, i) => {
            if (c.selected !== undefined)
                c.selected = "" + i;
            return c;
        });
        setSelectedRows([]);  // All selected elements are now removed, easy.
        setFiles(newFiles);
    }

    function swapFileIndices(farr: Filename[], i: number, j: number) {
        const t = farr[i];
        farr[i] = farr[j];
        farr[j] = t;
        if (farr[i].selected !== undefined)
            farr[i].selected = "" + i;
        if (farr[j].selected !== undefined)
            farr[j].selected = "" + j;
    }

    function moveUpSelected() {
        const selectedRowIds = selectedRows.map((c, i) => c.selected);
        let couldSwapPreceding = !selectedRowIds.includes("0");
        const newFiles = [...files];
        for(let i = 1; i < files.length; i++){
            if (selectedRowIds.includes("" + i)){
                if (!selectedRowIds.includes("" + (i-1)) || couldSwapPreceding) {
                    swapFileIndices(newFiles, i-1, i);
                    couldSwapPreceding = true;
                } else {
                    couldSwapPreceding = false;
                }
            }
        }
        setSelectedRows([]);  // Invalidate and recalculate, expensive!
        setFiles(newFiles);
    }

    function moveDownSelected() {
        const selectedRowIds = selectedRows.map((c, i) => c.selected);
        let couldSwapPreceding = !selectedRowIds.includes("" + (files.length - 1));
        const newFiles = [...files];
        for(let i = files.length - 2; i >= 0; i--){
            if (selectedRowIds.includes("" + i)){
                if (!selectedRowIds.includes("" + (i+1)) || couldSwapPreceding) {
                    swapFileIndices(newFiles, i+1, i);
                    couldSwapPreceding = true;
                } else {
                    couldSwapPreceding = false;
                }
            }
        }
        setSelectedRows([]);  // Invalidate and recalculate, expensive!
        setFiles(newFiles);
    }

    useEffect(() => {
        const delayedNameValidityUpdate = setTimeout(() => {
            if (debounceNameInput[0] !== undefined)
                requestNameValidity(debounceNameInput[0]);
        }, 500)

        return () => clearTimeout(delayedNameValidityUpdate)
    }, [debounceNameInput]);

    useEffect(() => {
        const actualFiles = files.filter((e, i, a) => {return e.suggestion != ""});
        if (actualFiles.length == 1) {
            // Single-file torrent!
            if (actualFiles[0].path != ""){
                // Use the user override, if available.
                setOnlyFile(actualFiles[0].path.replace(/^.*[\\/]/, ""));
            } else {
                // Otherwise, just go with the filename.
                setOnlyFile(actualFiles[0].suggestion);
            }
        } else {
            setOnlyFile(undefined);
        }
    }, [files]);

    return (
        <Dialog {...props}>
            <DialogContent className="sm:max-w-6xl">
                <DialogHeader>
                    <DialogTitle>{t("CreateTorrent")}</DialogTitle>
                    <DialogDescription className="break-all text-xs"></DialogDescription>
                </DialogHeader>

                <ScrollArea className="max-h-[512px]">
                    <div className="flex flex-col gap-4 mx-4">
                        <Label htmlFor="destination" className="whitespace-nowrap pr-5 pt-2">
                            {t("Destination")}
                        </Label>
                        <PathInput path={destination} onPathChange={setDestination} />

                        <Label htmlFor="name" className="whitespace-nowrap pr-5 pt-2">
                            {t("Name")}
                        </Label>
                        <div className="relative flex items-center">
                            <Input
                                id="name"
                                hidden={onlyFile !== undefined}
                                disabled={onlyFile !== undefined}
                                className="grow pl-6"
                                onChange={(event) => {
                                    setName(event.target.value);
                                    setPending(event.target);
                                    setDebounceNameInput([event.target, event.target.value]);
                                }}
                            />
                            <div className="absolute left-2" hidden={onlyFile !== undefined}>
                                {isNameValid == NameValid.Valid ? <Icons.checkmark /> : (
                                    isNameValid == NameValid.Invalid ? <Icons.redcross /> : <Icons.spinner />
                                )}
                            </div>
                            <div className="absolute left-2" hidden={onlyFile === undefined}>
                                <Label> {onlyFile} </Label>
                            </div>
                        </div>

                        <Label htmlFor="files" className="whitespace-nowrap pr-5 pt-2">
                            {t("Files")}
                        </Label>
                        <SimpleTable data={files} columns={filenameColumns} />
                        <div className="flex">
                            <Button variant="outline" type="button" className={files.length === 0 ? "animate-bounce mr-4" : "mr-4"} onClick={() => {
                                    addFile();
                                }}>
                                <Plus />
                            </Button>
                            <div className="grow"></div>
                            <Button variant="outline" type="button" disabled={hasNoSelection} onClick={moveUpSelected}>
                                <ArrowUp />
                            </Button>
                            <Button variant="outline" type="button" disabled={hasNoSelection} className="mr-4" onClick={moveDownSelected}>
                                <ArrowDown />
                            </Button>
                            <Button variant="outline" type="button" disabled={hasNoSelection} className="bg-destructive-foreground" onClick={removeSelected}>
                                <Trash2 className="stroke-destructive" />
                            </Button>
                        </div>

                        <details className="col-span-2">
                            <summary>{t("Advanced")}</summary>

                            <Label htmlFor="description" className="whitespace-nowrap pr-5 pt-2">
                                {t("Description")}
                            </Label>
                            <Textarea
                                id="description"
                                className="col-span-2"
                                value={description}
                                onChange={(event) => setDescription(event.target.value)}
                            />

                            <Label htmlFor="trackers" className="whitespace-nowrap pr-5 pt-2">
                                {t("Trackers")}
                            </Label>
                            <Textarea
                                id="trackers"
                                placeholder="http://tracker.com/announce&#10;udp://anothertracker:8080/&#10; ..."
                                className="col-span-2"
                                value={trackers}
                                onChange={(event) => setTrackers(event.target.value.replace(/[^\S\r\n]/g, ""))}
                            />

                            <Label htmlFor="initialNodes" className="whitespace-nowrap pr-5 pt-2">
                                {t("InitialNodes")}
                            </Label>
                            <Textarea
                                id="initialNodes"
                                className="col-span-2"
                                placeholder='your.router.node 4804&#10;2001:db8:100:0:d5c8:db3f:995e:c0f7 1941&#10; ...'
                                value={initialNodes}
                                onChange={(event) => setInitialNodes(event.target.value)}
                            />
                        </details>
                    </div>
                </ScrollArea>

                <DialogFooter>
                    <Button
                        variant="outline"
                        type="submit"
                        onClick={() => {
                            triblerService
                                .createTorrent(
                                    onlyFile === undefined ? name : onlyFile,
                                    description,
                                    files.filter((e, i, a) => {return e.src != ""}).map((f) => f.path),
                                    files.filter((e, i, a) => {return e.src != ""}).map((f) => f.src),
                                    destination,
                                    trackers.split(/\r?\n/),
                                    initialNodes.split(/\r?\n/)
                                )
                                .then((response) => {
                                    if (response === undefined) {
                                        toast.error(
                                            `${t("ToastErrorCreateTorrent", {name: name})} ${t("ToastErrorGenNetworkErr")}`
                                        );
                                    } else if (isErrorDict(response)) {
                                        // Quinten: according to the typing, response could not be a ErrorDict here?!
                                        toast.error(
                                            `${t("ToastErrorCreateTorrent", {name: name})} ${(response as ErrorDict).error.message}`
                                        );
                                    }
                                });
                            if (props.onOpenChange) props.onOpenChange(false);
                        }}
                        disabled={(files.filter((e, i, a) => {return e.suggestion != ""}).length === 0 || isNameValid != NameValid.Valid) && onlyFile === undefined}>
                        {t("CreateTorrentButton")}
                    </Button>
                    <DialogClose asChild>
                        <Button variant="outline" type="button">
                            {t("Cancel")}
                        </Button>
                    </DialogClose>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
