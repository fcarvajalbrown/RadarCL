# Architecture Decision Records

| # | Title | Status |
|---|-------|--------|
| [0001](0001-pyside6-gui-stack.md) | PySide6 (Qt6) as the GUI stack | Accepted |
| [0002](0002-async-core-qthread-worker-bridge.md) | Async core with a QThread worker bridge | Accepted |
| [0003](0003-crawl-phase1-phase2-scope.md) | Two-phase crawl scope (.cl-only, then optional expansion) | Accepted |
| [0004](0004-verification-staging-unknown-not-invalid.md) | Staged verification with UNKNOWN as a first-class outcome | Superseded by 0007 |
| [0005](0005-hardware-aware-auto-tuning.md) | Hardware-aware auto-tuning of crawl settings | Accepted |
| [0006](0006-sqlite-session-store-last-10-pruning.md) | SQLite session store with last-10 pruning | Accepted |
| [0007](0007-smtp-response-classification.md) | SMTP response classification by reply-code class | Superseded by 0009 |
| [0008](0008-vendored-core-dependencies.md) | Vendored core dependencies, hash-pinned GUI dependencies | Accepted |
| [0009](0009-mx-resolution-failure-is-unknown.md) | MX resolution failure is UNKNOWN, with fallback transports | Accepted |
| [0010](0010-export-contents-differ-by-format.md) | Export contents differ by format: CSV is the mailable list, JSON and HTML are the run record | Accepted |
| [0011](0011-ct-fallback-and-source-hygiene.md) | Certificate Transparency fallback and curated source hygiene | Accepted |
| [0012](0012-curated-sources-assert-identity.md) | Curated sources assert their identity, not just their availability | Superseded by 0013 |
| [0013](0013-curated-source-stage-removed-after-measurement.md) | The curated-source stage is removed after measuring it | Accepted |
| [0014](0014-country-is-never-inferred-from-a-com-address.md) | Country is never inferred from a `.com` address | Accepted |
