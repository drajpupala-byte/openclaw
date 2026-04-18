from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from core.transaction import Transaction


class BaseParser(ABC):
    @abstractmethod
    def parse(self, filepath: Path) -> List[Transaction]:
        """Parse a statement file and return a list of transactions."""
