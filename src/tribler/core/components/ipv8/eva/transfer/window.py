from typing import List, Optional


class TransferWindow:
    def __init__(self, start: int, size: int):
        self.blocks: List[Optional[bytes]] = [None] * size

        self.start = start
        self.processed: int = 0

    def add(self, index: int, block: bytes):
        if self.blocks[index] is not None:
            return
        self.blocks[index] = block
        self.processed += 1

    def is_finished(self) -> bool:
        return self.processed == len(self.blocks)

    def consecutive_blocks(self):
        for block in self.blocks:
            if block is None:
                break
            yield block

    def __str__(self):
        return f'{{start: {self.start}, processed: {self.processed}, size: {len(self.blocks)}}}'
