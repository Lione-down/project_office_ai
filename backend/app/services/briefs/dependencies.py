from dataclasses import dataclass


@dataclass(frozen=True)
class BriefServices:
    skills: object
    generation: object | None
