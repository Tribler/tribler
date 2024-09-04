import { RouterProvider } from "react-router-dom";
import { ThemeProvider } from "./contexts/ThemeContext";
import { router } from "./Router";
import { LanguageProvider } from "./contexts/LanguageContext";
import { Button } from "@/components/ui/button";
import { useTranslation } from "react-i18next";

import './i18n';

function collapseError(){
    const error_popup = document.querySelector("#error_popup");
    if (error_popup && !error_popup.classList.contains("hidden")) {
        // Hide if we are not hidden
        error_popup.classList.toggle("hidden");
    }
}

function reportError() {
    const error_popup_text = document.querySelector("#error_popup_text");
    if (error_popup_text){
        const err_text = "Hi! I was using Tribler and THIS happened! :cry:\r\n```\r\n" + error_popup_text.textContent + "\r\n```";
        const url = encodeURI("https://github.com/Tribler/tribler/issues/new?body=" + err_text);
        window.open(url, '_blank')?.focus();
    }
    collapseError();
}

function searchError() {
    const error_popup_text = document.querySelector("#error_popup_text");
    if (error_popup_text?.textContent){
        const err_lines = error_popup_text.textContent.split(/\r?\n/);
        var url = "";

        if (err_lines.length > 1){
            const err_file_raw = err_lines[err_lines.length-4];
            const last_f_name = Math.max(err_file_raw.lastIndexOf('/'), err_file_raw.lastIndexOf('\\'));
            const err_file = err_file_raw.substring(last_f_name + 1).replace(/"/g,'').replace(/,/g,'');

            const err_exception = err_lines[err_lines.length-2];

            url = encodeURI("https://github.com/Tribler/tribler/issues?q=is:issue+" + err_file + "+" + err_exception);
        } else {
            url = encodeURI("https://github.com/Tribler/tribler/issues?q=is:issue+" + error_popup_text.textContent);
        }
        window.open(url, '_blank')?.focus();
    }
}

export default function App() {
    const { t } = useTranslation();

    return (
        <LanguageProvider>
            <div id="error_popup" role="alert" className="overflow-hidden mx-8 mt-2 h-10 hover:h-96 hidden transition-height duration-500 ease-in-out">
                <div className="bg-red-500 text-white font-bold rounded-t px-4 py-2">
                    {t("ErrorNotification")}
                </div>
                <div className="border border-t-0 border-red-400 rounded-b bg-card px-4 py-3 text-red-600" style={{whiteSpace: "pre"}}>
                    <p id="error_popup_text" className="overflow-y-scroll max-h-64"></p>
                    <div className="w-1/2 justify-start">
                        <Button className="h-10 pl-2 my-2 w-1/3 mx-2 justify-start rounded-none text-muted-foreground bg-secondary" variant="outline" onClick={searchError}>
                            {t("ErrorSearchButton")}
                        </Button>
                        <Button className="h-10 pl-2 my-2 w-1/3 mx-2 justify-start rounded-none text-muted-foreground bg-secondary" variant="outline" onClick={reportError}>
                            {t("ErrorReportButton")}
                        </Button>
                        <Button className="h-10 pl-2 my-2 w-1/3 mx-2 justify-start rounded-none text-muted-foreground bg-secondary" variant="outline" onClick={collapseError}>
                            {t("ErrorIgnoreButton")}
                        </Button>
                    </div>
                </div>
            </div>
            <ThemeProvider>
                <RouterProvider router={router} />
            </ThemeProvider>
        </LanguageProvider>
    )
}
