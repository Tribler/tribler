import {Button} from "@/components/ui/button";
import toast from "react-hot-toast";
import {useTranslation} from "react-i18next";

interface SaveButtonProps {
    onClick: () => Promise<void>;
}

export default function SaveButton(props: SaveButtonProps) {
    const {t} = useTranslation();

    const save = () => {
        (async () => {
            toast.promise(props.onClick(), {
                loading: t("SettingsSaving"),
                success: <b>{t("SettingsSaved")}</b>,
                error: <b>{t("SettingsSaveFailed")}</b>,
            });
        })();
    };

    return (
        <>
            <Button type="submit" className="mt-2" onClick={save}>
                {t("Save")}
            </Button>
        </>
    );
}
