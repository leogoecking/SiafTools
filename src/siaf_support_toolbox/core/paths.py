from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AppPaths:
    root: Path
    data: Path
    logs: Path
    exports: Path

    @classmethod
    def for_user(cls) -> AppPaths:
        override = os.environ.get("SIAF_TOOLBOX_HOME")
        base = (
            Path(override)
            if override
            else Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SIAF Support Toolbox"
        )
        return cls(root=base, data=base / "data", logs=base / "logs", exports=base / "exports")

    def ensure(self) -> AppPaths:
        for path in (self.root, self.data, self.logs, self.exports):
            path.mkdir(parents=True, exist_ok=True)
        return self
