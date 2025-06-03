from dataclasses import dataclass

@dataclass
class Skill:
    id: str                     # T.ex. O*NET Element ID eller liknande
    name: str
    description: str = ""
