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
    def posted_dt(self):
        """Parse `posted` (ISO string, epoch seconds or epoch millis) to aware UTC datetime, or None."""
        from datetime import datetime, timezone
        v = str(self.posted or "").strip()
        if not v:
            return None
        try:
            if v.replace(".", "", 1).isdigit():
                n = float(v)
                return datetime.fromtimestamp(n / 1000 if n > 1e11 else n, timezone.utc)
            d = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    @property
    def key(self):
        return f"{self.source}:{self.external_id}"
