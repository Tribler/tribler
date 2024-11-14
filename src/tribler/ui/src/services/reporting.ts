import axios, { AxiosError } from "axios";

export interface ErrorDict { [error: string]: {handled: boolean, message: string}; };

export function isErrorDict(object: any): object is ErrorDict {
    return (typeof object === 'object') && ('error' in object);
}

export function handleHTTPError(error: Error | AxiosError) {
    const error_popup_text = document.querySelector("#error_popup_text");
    if (!error_popup_text){
        return;
    }
    if (axios.isAxiosError(error) && error.response?.data?.error?.message){
        error_popup_text.textContent = error.response.data.error.message.replace(/(?:\n)/g, '\r\n');
    } else {
        var stack = "";
        if (error.stack)
            stack = error.stack.replace(/(?:\n)/g, '\r\n');
        error_popup_text.textContent = error.message + "\n" + stack;
    }
    const error_popup = document.querySelector("#error_popup");
    if (error_popup && error_popup.classList.contains("hidden")) {
        // Unhide if we were hidden
        error_popup.classList.toggle("hidden");
    }
}

export function formatAxiosError(error: Error | AxiosError): ErrorDict | undefined {
    if (axios.isAxiosError(error)) {
         if (!error.response) {
            // This is a network error, see https://github.com/axios/axios?tab=readme-ov-file#error-types
            // We don't need to do anything, but the GUI should not crash on this
            return undefined;
         }
         if (error.response.data?.error?.handled == false) {
            // This is an error that conforms to the internal unhandled error format: ask the user what to do
            handleHTTPError(error);
         }
         // This is some (probably expected) REST API error
         return error.response.data;
     }
     // No idea what this is: make it someone else's problem
     throw error;
}
