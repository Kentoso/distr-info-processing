import hashlib
from dataclasses import dataclass, field


@dataclass(slots=True)
class BloomFilter:
    m: int
    k: int
    bits: bytearray = field(init=False, repr=False)
    item_count: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        if self.m <= 0:
            raise ValueError("m must be positive")
        if self.k <= 0:
            raise ValueError("k must be positive")
        self.bits = bytearray(self.m)
        self.item_count = 0

    def _hashes(self, item: str) -> list[int]:
        data = item.encode("utf-8")
        indices: list[int] = []
        for i in range(self.k):
            digest = hashlib.sha256(f"hash-{i}:".encode("utf-8") + data).digest()
            indices.append(int.from_bytes(digest, "big") % self.m)
        return indices

    def add(self, item: str) -> None:
        for index in self._hashes(item):
            self.bits[index] = 1
        self.item_count += 1

    def probably_contains(self, item: str) -> bool:
        return all(self.bits[index] for index in self._hashes(item))

    def bit_density(self) -> float:
        return sum(self.bits) / self.m
