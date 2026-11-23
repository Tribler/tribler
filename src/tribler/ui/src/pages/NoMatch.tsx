import {buttonVariants} from "@/components/ui/button";
import {NavLink} from "react-router-dom";
import {useTranslation} from "react-i18next";

export default function NoMatch() {
    const {t} = useTranslation();

    return (
        <div className="bg-background text-foreground flex-grow flex items-center justify-center">
            <div className="space-y-4">
                <h2 className="text-8xl mb-4">404</h2>
                <h1 className="text-3xl font-semibold">{t("PageNotFound")}</h1>
                <p className="text-sm text-muted-foreground">{t("PageNotFoundDescription")}</p>
                <NavLink to="/" className={buttonVariants()}>
                    {t("BackToHome")}
                </NavLink>
            </div>
        </div>
    );
}
