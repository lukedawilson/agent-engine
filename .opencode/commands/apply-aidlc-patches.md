---
description: Apply AI-DLC rule patches sequentially from .aidlc/aidlc-patches/
---

Apply all numbered patches from `.aidlc/aidlc-patches/` in sequence:

!`./apply-patches.sh`

Report which patches were applied and which were already present. If any patch fails due to a conflict, stop and report the conflict.
