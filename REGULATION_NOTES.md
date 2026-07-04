# REGULATION_NOTES.md

## 25 kW Limit
- **YAML Field**: `max_capacity_kw`
- **Description**: Unlicensed production capacity limit. Currently set to 25 kW for rooftop installations under 5.1.j/5.1.ç regulations. Different limits may apply for ground-mount installations under 5.1.h.
- **Enforcement**: If the proposed system size exceeds this value, it results in a non-compliance violation.

## Transformer Capacity Check
- **YAML Field**: `transformer_capacity_check_ratio`
- **Description**: The system size must not exceed a certain percentage of the transformer capacity (kVA).
- **Enforcement**: System size (kW) must be <= Transformer Capacity (kVA) * `transformer_capacity_check_ratio`.

## Mahsuplaşma / Netting & Self-Consumption
- **YAML Fields**: `netting_mode`, `self_consumption_ratio_min`
- **Description**: `netting_mode` determines whether the generation is netted against consumption on an `hourly` or `monthly` basis. For connection types marked as `self_consumption_limited`, the `self_consumption_ratio_min` enforces a minimum ratio of self-consumed energy (0.0 to 1.0).
- **Enforcement**: If applicable, the calculated self-consumption ratio must not fall below `self_consumption_ratio_min`. The `netting_mode` is consumed downstream by the finance module.

## Hybrid / Storage
- **YAML Field**: `hybrid_storage_allowed`
- **Description**: Specifies whether PV + Storage (hybrid) installations are allowed under current regulation for the given mount type.
- **Enforcement**: If a hybrid storage system is proposed and this flag is `false`, it results in a violation.

## Ground-Mount Eligibility
- **YAML Field**: `ground_mount_eligibility`
- **Description**: For ground-mount (arazi) installations, specific regulatory flags must be met, modeled as a checklist:
  - `industrial_or_agricultural_use`: The facility must be for industrial or agricultural use.
  - `zoning_status_approved`: Zoning status must be approved for the land.
  - `eia_approved`: Environmental Impact Assessment (ÇED) must be approved.
- **Enforcement**: If any of these required flags are set to `true` in the configuration but not met by the site parameters, the system is deemed non-compliant.
