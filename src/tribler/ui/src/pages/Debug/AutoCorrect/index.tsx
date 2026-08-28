import {useState} from "react";
import {triblerService} from "@/services/tribler.service";
import {isErrorDict} from "@/services/reporting";
import {useInterval} from "@/hooks/useInterval";


export default function AutoCorrect() {
    const [vocabularyPrefixes, setVocabularyPrefixes] = useState<string[]>([]);
    const [vocabularyContinuations, setVocabularyContinuations] = useState<string[]>([]);

    const internal = ["</s>", "<s>", "<unk>"];

    useInterval(
        async () => {
            const response = await triblerService.getVocabulary();
            if (!(response === undefined) && !isErrorDict(response)) {
                setVocabularyPrefixes(response.filter((word) => word.startsWith("▁") && word.length > 1).sort());
                setVocabularyContinuations(response.filter((word) => !word.startsWith("▁") && !internal.includes(word)).sort());
            }
        },
        5000,
        true
    );

    return (
        <div className="w-full h-full p-2">
            <span className="flex flex-wrap justify-center pt-8 text-6xl font-black uppercase tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-red-500 via-yellow-400 via-green-500 via-blue-500 to-purple-600 bg-[length:200%_auto] animate-rainbow-shift">
                {"AutoCorrect Vocabulary".split('').map((char, index) => {
                    if (char === ' ') {
                        return <span key={index} className="w-6" aria-hidden="true" />;
                    }

                    return (
                       <span key={index} className="relative inline-block select-none text-[inherit] animate-wordart-wave transition-transform after:absolute after:left-0 after:top-0 after:-z-10 after:text-transparent after:[-webkit-text-stroke:2px_#000] after:[text-shadow:1px_1px_0_#000,2px_2px_0_#000,3px_3px_0_#000,4px_4px_0_#000,5px_5px_0_#000,6px_6px_0_#000]" after-content={`'${char.toUpperCase()}'`} style={{ animationDelay: `${index * 0.08}s` }}>
                            {char}
                        </span>
                    );
                })}
            </span>
            <p className="text-sm font-medium">Word stems:</p>
            {
                vocabularyPrefixes.map((elem, index) => {
                    return <span key={index} className="inline-flex items-center m-1 rounded-md bg-card px-2 py-1 text-xs font-medium text-card-foreground inset-ring inset-ring-gray-500/10">{elem.substr(1)}</span>;
                })
            }
            <br />
            <p className="text-sm font-medium mt-4">Suffixes:</p>
            {
                vocabularyContinuations.map((elem, index) => {
                    return <span key={index} className="italic inline-flex items-center m-1 rounded-md bg-linear-to-r from-card to-90% to-accent  px-2 py-1 text-xs font-medium text-card-foreground inset-ring inset-ring-gray-500/10">{elem}</span>;
                })
            }
        </div>
    );
}
