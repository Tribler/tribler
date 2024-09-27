import { useEffect, useRef } from 'react'


export default function Pieces({ pieces64, numpieces }: { pieces64: string, numpieces: number }) {
    const ref = useRef<HTMLCanvasElement>(null)

    const convertPieces = (pieces64: string, numpieces: number) => {
        if (pieces64 === undefined) { return [] }

        // Remove trailing '='
        pieces64 = pieces64.replace(/\=+$/, '');

        const pieces = [];
        const pieceString = atob(pieces64);
        for (let i = 0; i < Math.min(numpieces, pieceString.length); ++i) {
            const pieceNumber = pieceString[i].charCodeAt(0);
            for (let j = 8 - 1; j >= 0; --j) {
                pieces.push(pieceNumber & 1 << j ? 1 : 0);
            }
        }
        return pieces;
    }

    useEffect(() => {
        if (ref.current) {
            const canvas = ref.current.getContext('2d');
            const pieces = convertPieces(pieces64, numpieces);
            if (!canvas || !pieces || pieces.length === 0) { return; }

            // Get size from the HTML canvas element
            const width = canvas.canvas.width;
            const height = canvas.canvas.height;
            const numPieces = numpieces;

            if (numPieces <= width) {
                const pieceWidth = width / numPieces;
                pieces.forEach(function (piece, index) {
                    if (piece) {
                        canvas.fillStyle = 'hsl(26, 100%, 50%)';
                        canvas.fillRect(index * pieceWidth, 0, Math.ceil(pieceWidth), height);
                    }
                });
            } else {
                const piecesPerPixel = numPieces / width;
                const piecesPerPixelFloor = Math.floor(piecesPerPixel);
                for (let index = 0; index < width; index++) {
                    const beginPiece = Math.floor(piecesPerPixel * index);
                    const endPiece = Math.floor(beginPiece + piecesPerPixel);
                    let pieceSum = 0;
                    for (let j = beginPiece; j < endPiece; j++) {
                        pieceSum += pieces[j];
                    }
                    canvas.fillStyle = 'hsl(26, 100%, ' + (100 - (50 * ((pieceSum / piecesPerPixelFloor)))) + '%)';
                    canvas.fillRect(index, 0, 10, height);
                }
            }
        }
    }, [pieces64, numpieces])

    return <canvas ref={ref} style={{ height: '20px', width: '97%', background: 'white', border: '1px solid #2f2f2f' }} />
}

