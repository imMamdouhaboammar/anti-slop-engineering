# Privacy & Data Lineage Gate Playbooks

> Operational and architectural playbooks executing Apple Privacy and Meta Data Infrastructure engineering disciplines.

## Playbook Catalog

1. **[Apple Privacy Engineering Playbook](apple-privacy-playbook.md)**
   - On-device processing hierarchy and hardware security enclave boundaries.
   - Local Differential Privacy ($\epsilon \le 1.0$) parameterization and noise generation.
   - Apple Private Click Measurement and zero-identifier telemetry.

2. **[Meta Data Infrastructure Playbook](meta-data-infra-playbook.md)**
   - Lineage DAG generation and flow policy compilation.
   - Key-per-Subject Crypto-Shredding KMS operational lifecycle.
   - Automated retention TTL garbage collection pipelines across lakehouse partitions.

3. **[Privacy Booby Traps Reference](references/privacy-booby-traps.md)**
   - The Top 10 silent privacy vulnerabilities: Soft-delete illusion, Logging `req.body`, Telemetry identifier leakage, Query parameter leaks, and Indefinite backups.
