import { useRef, useState } from "react";
import { Button } from "./button";
import { SearchIcon } from "lucide-react";


export function Autocomplete({ placeholder, completions, onChange }: { placeholder: string, completions: (filter: string) => Promise<string[]>, onChange: (query: string) => void }) {
    const [inputValue, setInputValue] = useState<string>('');
    const [suggestions, setSuggestions] = useState<string[]>([]);
    const [selectedSuggestion, setSelectedSuggestion] = useState<number>(0);
    const [focus, setFocus] = useState<boolean>(false);

    const inputRef = useRef<HTMLInputElement>(null)

    const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const value = event.target.value;
        setInputValue(value);
        if (value.length === 0) {
            setSuggestions([]);
            return;
        }

        // TODO: bebounce
        (async () => {
            setSuggestions(await completions(value));
        })();

    };

    const handleSuggestionClick = (value: string) => {
        setInputValue(value);
        setSuggestions([]);
        setSelectedSuggestion(0);
        onChange(value);
    };


    return (
        <div className="container px-4 md:px-8 flex h-14 items-stretch">
            <div className="flex h-full w-full flex-col rounded-md text-popover-foreground overflow-visible bg-transparent">
                <div className="group rounded-md border border-input px-3 py-2 text-sm ring-offset-background focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-tribler">
                    <div className="flex flex-wrap gap-1">
                        <input placeholder={placeholder}
                            className="ml-2 flex-1 bg-transparent outline-none placeholder:text-muted-foreground"
                            spellCheck="false"
                            onChange={handleInputChange}
                            onFocus={() => setFocus(true)}
                            onBlur={() => setFocus(false)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                    const query = (selectedSuggestion > 0) ? suggestions[selectedSuggestion - 1] : inputValue;
                                    handleSuggestionClick(query);
                                    inputRef.current?.blur();
                                }
                                else if ((e.key === 'ArrowDown')) {
                                    setSelectedSuggestion(Math.min(selectedSuggestion + 1, suggestions.length));
                                    e.preventDefault()
                                }
                                else if ((e.key === 'ArrowUp')) {
                                    setSelectedSuggestion(Math.max(selectedSuggestion - 1, 0));
                                    e.preventDefault()
                                }
                            }}
                            value={inputValue}
                            ref={inputRef}
                        />
                        <Button
                            variant="ghost"
                            className="h-6 py-0 px-0
                                       hover:outline hover:outline-neutral-500 outline-1 outline-offset-1
                                       active:outline active:outline-neutral-900 dark:active:outline-neutral-200"
                            onClick={() => {
                                const query = (selectedSuggestion > 0) ? suggestions[selectedSuggestion - 1] : inputValue;
                                handleSuggestionClick(query);
                                inputRef.current?.blur();
                            }}
                        >
                            <SearchIcon className="h-5" />
                        </Button>
                    </div>
                </div>
                {focus && suggestions.length > 0 &&(
                    <div className="relative mt-2">
                        <div className="max-h-[300px] overflow-y-auto overflow-x-hidden absolute top-0 z-10 w-full rounded-md border bg-popover text-popover-foreground shadow-md outline-none animate-in">
                            {suggestions.length > 0 && (suggestions.map((suggestion, index) => (
                                <div className={`p-1 text-foreground h-full overflow-auto  ${(selectedSuggestion === index + 1) ? 'bg-accent' : ''}`} key={index + 'a'}>
                                    <div className="relative flex select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none cursor-pointer"
                                        onClick={() => handleSuggestionClick(suggestion)}
                                        onMouseDown={(event) => event.preventDefault()}
                                        key={index + 'b'}>
                                        {suggestion}
                                    </div>
                                </div>
                            )))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
