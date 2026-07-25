from dataclasses import dataclass
from datetime import datetime


@dataclass
class Project:
    id: str
    name: str
    status: str  # WAITING, IMPLEMENTING, VERIFIED
    created_at: datetime
