import axios, { AxiosError } from "axios";

export function handleHTTPError(error: Error | AxiosError) {
    const error_popup_text = document.querySelector("#error_popup_text");
    if (!error_popup_text){
        return Promise.reject(error);
    }
    if (axios.isAxiosError(error) && error.response?.data?.error?.message){
        error_popup_text.textContent = error.response.data.error.message.replace(/(?:\n)/g, '\r\n');
    } else {
        error_popup_text.textContent = `${error}`;
    }
    const error_popup = document.querySelector("#error_popup");
    if (error_popup && error_popup.classList.contains("hidden")) {
        // Unhide if we were hidden
        error_popup.classList.toggle("hidden");
    }
    return Promise.reject(error);
}
