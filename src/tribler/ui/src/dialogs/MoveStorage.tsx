import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { DialogProps } from "@radix-ui/react-dialog";
import { JSX } from "react/jsx-runtime";
import { Label } from "@/components/ui/label";
import { useTranslation } from "react-i18next";
import { PathInput } from "@/components/path-input";
import { useEffect, useState } from "react";
import { Download } from "@/models/download.model";
import { TFunction } from "i18next";
import { Checkbox } from "@/components/ui/checkbox";

interface MoveStorageProps {
    selectedDownloads: Download[];
    onMove: (selectedDownloads: Download[], storageLocation: string, completedLocation: string, t: TFunction) => void;
}

export default function MoveStorage(props: JSX.IntrinsicAttributes & DialogProps & MoveStorageProps) {
    const { t } = useTranslation();
    const [storageLocation, setStorageLocation] = useState("");
    const [completedLocation, setCompletedLocation] = useState("");
    const [moveCompleted, setMoveCompleted] = useState<boolean>(false);

    useEffect(() => {
        if (props.open) {
            const destination = props.selectedDownloads[0]?.destination || "";
            const completed_dir = props.selectedDownloads[0]?.completed_dir || "";
            setStorageLocation(destination);
            setCompletedLocation(completed_dir);
            setMoveCompleted(destination !== completed_dir && completed_dir.length !== 0);
        }
    }, [props.open]);

    return (
        <Dialog open={props.open} onOpenChange={props.onOpenChange}>
            <DialogContent className="max-w-3xl">
                <DialogHeader>
                    <DialogTitle>{t("ChangeStorage")}</DialogTitle>
                    <DialogDescription>{t("ChangeStorageDescription")}</DialogDescription>
                </DialogHeader>
                <div className="flex items-center">
                    <Label htmlFor="dest_dir" className="w-64 whitespace-nowrap">
                        {t("ChangeStorageLocation")}
                    </Label>
                    <PathInput
                        className="col-span-5"
                        path={storageLocation}
                        onPathChange={(path) => setStorageLocation(path)}
                    />
                </div>
                <div className="flex items-center">
                    <div className="w-64 flex items-center">
                        <Checkbox
                            checked={moveCompleted}
                            id="move_completed"
                            onCheckedChange={(value) => setMoveCompleted(value === true)}
                        />
                        <label
                            htmlFor="move_completed"
                            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 whitespace-nowrap pl-2"
                        >
                            {t("MoveAfterCompletion")}
                        </label>
                    </div>
                    <PathInput disabled={!moveCompleted} path={completedLocation} onPathChange={setCompletedLocation} />
                </div>
                <DialogFooter>
                    <Button
                        variant="outline"
                        type="submit"
                        disabled={props.selectedDownloads.every(
                            (d) =>
                                d.destination === storageLocation &&
                                d.completed_dir === completedLocation &&
                                (d.destination === d.completed_dir || d.completed_dir.length == 0) != moveCompleted
                        )}
                        onClick={() => {
                            props.onMove(
                                props.selectedDownloads,
                                storageLocation,
                                moveCompleted ? completedLocation : storageLocation,
                                t
                            );
                            props.onOpenChange?.(false);
                        }}
                    >
                        {t("ChangeStorageButton")}
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
