import { useEffect, useState, RefObject, useRef } from 'react'

export const useResizeObserver = ({ref, element}: {ref?: RefObject<HTMLElement>, element?: Element | null}) => {
    const observer = useRef<ResizeObserver | null>(null);
    const [rect, setRect] = useState<DOMRectReadOnly>();
    useEffect(() => {
        observer.current = new ResizeObserver((entries: ResizeObserverEntry[]) => {
            if (entries) {
                setRect(entries[0].contentRect);
            }
        });

        let observable  = (ref) ? ref.current : element;
        if (observable) {
            observer.current.observe(observable);
        }

        return () => {
            if (observer.current) {
                observer.current.disconnect();
            }
        }
    }, [ref, element]);

    return rect;
}
