import { useEffect, useRef } from "react";


export function useInterval(callback: Function, delay: number, startNow: boolean = false) {
    const savedCallback = useRef<Function>(callback);

    useEffect(() => {
        savedCallback.current = callback;
    }, [callback]);

    useEffect(() => {
        function tick() {
            savedCallback.current();
        }
        if (startNow) tick();
        if (delay !== null) {
            let id = setInterval(tick, delay);
            return () => {
                clearInterval(id)
            };
        }
    }, [delay]);
}
