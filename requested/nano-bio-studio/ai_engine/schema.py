from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class DesignSpace:
    size_nm_min: float
    size_nm_max: float
    charge_mV_min: float
    charge_mV_max: float

    materials: List[str] = field(default_factory=lambda: ["PLGA", "Lipid", "Gold"])
    ligands: List[str] = field(default_factory=lambda: ["None", "PEG", "Folate"])
    payloads: List[str] = field(default_factory=lambda: ["DrugA", "DrugB"])
    dose_min: float = 0.5
    dose_max: float = 20.0

    # Optional fixed/allowed values
    fixed: Dict[str, str] = field(default_factory=dict)

@dataclass
class ObjectiveWeights:
    efficacy: float = 0.5
    safety: float = 0.3
    cost: float = 0.2

    def normalized(self) -> "ObjectiveWeights":
        s = max(self.efficacy + self.safety + self.cost, 1e-9)
        return ObjectiveWeights(self.efficacy/s, self.safety/s, self.cost/s)
