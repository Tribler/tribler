import { RouterProvider } from "react-router-dom";
import { ThemeProvider } from "./contexts/ThemeContext";
import { router } from "./Router";
import { LanguageProvider } from "./contexts/LanguageContext";

import './i18n';

export default function App() {
    return (
        <LanguageProvider>
            <ThemeProvider>
                <RouterProvider router={router} />
            </ThemeProvider>
        </LanguageProvider>
    )
}
