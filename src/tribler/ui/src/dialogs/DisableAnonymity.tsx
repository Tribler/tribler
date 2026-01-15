import {
    Dialog,
    DialogClose,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {Button} from "@/components/ui/button";
import {DialogProps} from "@radix-ui/react-dialog";
import {JSX} from "react/jsx-runtime";
import {useTranslation} from "react-i18next";
import {Download} from "@/models/download.model";
import {TFunction} from "i18next";

interface DisableAnonymityProps {
    selectedDownloads: Download[];
    setHops: (selectedDownloads: Download[], hops: number, t: TFunction) => void;
}

export default function DisableAnonymity(props: JSX.IntrinsicAttributes & DialogProps & DisableAnonymityProps) {
    const {t} = useTranslation();

    return (
        <Dialog open={props.open} onOpenChange={props.onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>{t("DisableAnonymity")}</DialogTitle>
                    <DialogDescription>{t("DisableAnonymityConfirm")}</DialogDescription>
                </DialogHeader>
                <DialogFooter>
                    <Button
                        variant="outline"
                        type="submit"
                        onClick={() => {
                            props.setHops(props.selectedDownloads, 0, t);
                            props.onOpenChange?.(false);
                        }}>
                        {t("Continue")}
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
