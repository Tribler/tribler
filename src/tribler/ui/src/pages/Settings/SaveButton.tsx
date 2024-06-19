import { Button } from "@/components/ui/button";
import toast, { Toaster } from 'react-hot-toast';
import { useTranslation } from "react-i18next";


interface SaveButtonProps {
    onClick: () => Promise<void>;
}

export default function SaveButton(props: SaveButtonProps) {
    const { t } = useTranslation();

    const save = () => {
        (async () => {
            toast.promise(
                props.onClick(),
                {
                    loading: 'Saving...',
                    success: <b>Settings saved!</b>,
                    error: <b>Couldn't save settings.</b>,
                }
            );
        })();
    }

    return (
        <>
            <Button type="submit" className="mt-2" onClick={save}>{t('Save')}</Button>
            <Toaster
                position="bottom-left"
                toastOptions={{
                    className: 'bg-accent text-foreground font-light',
                }}
            />
        </>
    )
}