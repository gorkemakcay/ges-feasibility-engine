import yaml
from pathlib import Path
from typing import Optional

from gesfeas.input.models import SiteParameters, MountType, ConnectionType
from gesfeas.regulation.models import RegulationConfig, RegulationResult, GroundMountEligibility

def load_regulation_config(config_path: Path) -> RegulationConfig:
    """Loads a RegulationConfig from a YAML file."""
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return RegulationConfig(**data)

def evaluate_compliance(
    site: SiteParameters,
    system_size_kw: float,
    self_consumption_ratio: Optional[float],
    regulation_config: RegulationConfig,
    is_hybrid_storage: bool = False,
    ground_mount_flags: Optional[GroundMountEligibility] = None
) -> RegulationResult:
    """
    Evaluates whether a proposed PV (or PV+Storage) installation is compliant
    with Turkish EPDK unlicensed generation rules.
    """
    violations = []
    warnings = []

    # 1. max_capacity_kw
    if system_size_kw > regulation_config.max_capacity_kw:
        violations.append(
            f"max_capacity_kw: System size {system_size_kw} kW exceeds the allowed maximum of {regulation_config.max_capacity_kw} kW."
        )

    # 2. transformer_capacity_check
    max_allowed_by_transformer = site.transformer_capacity_kva * regulation_config.transformer_capacity_check_ratio
    if system_size_kw > max_allowed_by_transformer:
        violations.append(
            f"transformer_capacity_check: System size {system_size_kw} kW exceeds transformer capacity limit of {max_allowed_by_transformer} kW."
        )

    # 3. self_consumption_ratio_min
    if site.connection_type == ConnectionType.SELF_CONSUMPTION_LIMITED:
        if self_consumption_ratio is not None and self_consumption_ratio < regulation_config.self_consumption_ratio_min:
            violations.append(
                f"self_consumption_ratio_min: Self-consumption ratio {self_consumption_ratio:.2f} is below the minimum required {regulation_config.self_consumption_ratio_min:.2f}."
            )

    # 4. netting_mode
    # Netting mode is stored in config, used by finance later. (No direct compliance check needed here)

    # 5. hybrid_storage_allowed
    if is_hybrid_storage and not regulation_config.hybrid_storage_allowed:
        violations.append(
            "hybrid_storage_allowed: PV+Storage (hybrid) is not allowed under current regulation for this mount type."
        )

    # 6. ground_mount_eligibility
    if site.mount_type == MountType.GROUND and regulation_config.ground_mount_eligibility is not None:
        if ground_mount_flags is None:
            violations.append("ground_mount_eligibility: Missing eligibility flags for ground mount.")
        else:
            if regulation_config.ground_mount_eligibility.industrial_or_agricultural_use and not ground_mount_flags.industrial_or_agricultural_use:
                violations.append("ground_mount_eligibility: Must be for industrial or agricultural use.")
            if regulation_config.ground_mount_eligibility.zoning_status_approved and not ground_mount_flags.zoning_status_approved:
                violations.append("ground_mount_eligibility: Zoning status must be approved.")
            if regulation_config.ground_mount_eligibility.eia_approved and not ground_mount_flags.eia_approved:
                violations.append("ground_mount_eligibility: EIA (ÇED) must be approved.")

    is_compliant = len(violations) == 0
    return RegulationResult(is_compliant=is_compliant, violations=violations, warnings=warnings)
