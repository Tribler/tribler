import { useState } from "react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { useTranslation } from "react-i18next";
import SelectRemotePath from "@/dialogs/SelectRemotePath";


interface PathInputProps {
    path?: string;
    onPathChange?: (value: string) => void;
    directory?: boolean;
    className?: string;
}

export function PathInput(props: PathInputProps & JSX.IntrinsicAttributes) {
    const { t } = useTranslation();
    const [openPathDialog, setOpenPathDialog] = useState<boolean>(false);

    return (
        <div className={`flex w-full ${props.className ?? ''}`}>
            <SelectRemotePath
                initialPath={props.path || ""}
                selectDir={props.directory !== false}
                open={openPathDialog}
                onOpenChange={setOpenPathDialog}
                onSelect={(path) => {
                    if (props.onPathChange)
                        props.onPathChange(path)
                }}
            />
            <Input
                value={props.path}
                onChange={(event) => {
                    if (props.onPathChange)
                        props.onPathChange(event.target.value)
                }}
            />
            <Button
                className="ml-1"
                variant="outline"
                type="submit"
                onClick={() => {
                    setOpenPathDialog(true);
                }}
            >
                Browse
            </Button>
        </div>
    )
}
