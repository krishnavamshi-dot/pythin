from dataclasses import dataclass, field


@dataclass
class Job:
    source: str
    external_id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    remote: bool = False
    posted: str = ""
    employment_type: str = "full_time"  # full_time | cpt
    # filled in by screening
    role: str = ""
    score: float = 0.0
    reasons: list = field(default_factory=list)
    status: str = "new"

    @property
    def key(self):
        return f"{self.source}:{self.external_id}"
