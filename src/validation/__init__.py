from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pandas as pd
from pandas import DataFrame

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Container for validation results."""
    passed: bool
    check_name: str
    severity: str  # 'error', 'warning', 'info'
    details: Dict[str, Any]
    recommendation: Optional[str] = None


class DataValidator:

    def __init__(
        self,
        null_threshold_numeric: float = 0.15,
        null_threshold_categorical: float = 0.10,
        duplicate_tolerance: int = 0
    ):
        self.null_threshold_numeric = null_threshold_numeric
        self.null_threshold_categorical = null_threshold_categorical
        self.duplicate_tolerance = duplicate_tolerance
    
    # Validate DataFrame contains required columns with correct types
    def validate_schema(
        self,
        df: DataFrame,
        required_columns: List[str],
        column_types: Optional[Dict[str, str]] = None
    ) -> ValidationResult:
        missing = [col for col in required_columns if col not in df.columns]
        
        if missing:
            return ValidationResult(
                passed=False,
                check_name="schema_validation",
                severity="error",
                details={"missing_columns": missing, "available_columns": list(df.columns)},
                recommendation=f"Add missing columns: {missing}"
            )
        
        type_errors = []
        if column_types:
            for col, expected_type in column_types.items():
                if col in df.columns:
                    actual = str(df[col].dtype)
                    if expected_type not in actual:
                        type_errors.append({
                            "column": col,
                            "expected": expected_type,
                            "actual": actual
                        })
        
        if type_errors:
            return ValidationResult(
                passed=False,
                check_name="schema_validation",
                severity="warning",
                details={"type_mismatches": type_errors},
                recommendation="Review type conversions in processing pipeline"
            )
        
        return ValidationResult(
            passed=True,
            check_name="schema_validation",
            severity="info",
            details={"columns_validated": len(required_columns)}
        )
    
    # Validate null percentages are within acceptable thresholds
    def validate_nulls(
        self,
        df: DataFrame,
        numeric_columns: List[str],
        categorical_columns: List[str]
    ) -> List[ValidationResult]:
       
        results = []
        
        for col in numeric_columns:
            if col not in df.columns:
                continue
            
            null_pct = df[col].isnull().mean()
            if null_pct > self.null_threshold_numeric:
                results.append(ValidationResult(
                    passed=False,
                    check_name=f"null_check_{col}",
                    severity="error",
                    details={
                        "column": col,
                        "null_percentage": round(null_pct * 100, 2),
                        "threshold": self.null_threshold_numeric * 100
                    },
                    recommendation=f"Review imputation strategy for {col}"
                ))
        
        for col in categorical_columns:
            if col not in df.columns:
                continue
            
            null_pct = df[col].isnull().mean()
            if null_pct > self.null_threshold_categorical:
                results.append(ValidationResult(
                    passed=False,
                    check_name=f"null_check_{col}",
                    severity="warning",
                    details={
                        "column": col,
                        "null_percentage": round(null_pct * 100, 2),
                        "threshold": self.null_threshold_categorical * 100
                    }
                ))
        
        if not results:
            results.append(ValidationResult(
                passed=True,
                check_name="null_validation",
                severity="info",
                details={"message": "All null percentages within thresholds"}
            ))
        
        return results
    
    # Validate no duplicates exist
    def validate_duplicates(
        self,
        df: DataFrame,
        key_columns: List[str]
    ) -> ValidationResult:
        if not all(col in df.columns for col in key_columns):
            missing = [c for c in key_columns if c not in df.columns]
            return ValidationResult(
                passed=False,
                check_name="duplicate_validation",
                severity="error",
                details={"missing_key_columns": missing}
            )
        
        duplicates = df.duplicated(subset=key_columns, keep=False)
        dup_count = duplicates.sum()
        
        if dup_count > self.duplicate_tolerance:
            return ValidationResult(
                passed=False,
                check_name="duplicate_validation",
                severity="error",
                details={
                    "duplicate_count": int(dup_count),
                    "tolerance": self.duplicate_tolerance,
                    "sample_duplicates": df[duplicates][key_columns].head(5).to_dict('records')
                },
                recommendation="Run deduplication pipeline before proceeding"
            )
        
        return ValidationResult(
            passed=True,
            check_name="duplicate_validation",
            severity="info",
            details={"duplicate_count": int(dup_count)}
        )
    
    # Validate foreign key values exist in reference set
    def validate_referential_integrity(
        self,
        df: DataFrame,
        foreign_key_col: str,
        reference_values: set
    ) -> ValidationResult:
        if foreign_key_col not in df.columns:
            return ValidationResult(
                passed=False,
                check_name="referential_integrity",
                severity="error",
                details={"missing_column": foreign_key_col}
            )
        
        invalid = set(df[foreign_key_col].dropna()) - reference_values
        
        if invalid:
            return ValidationResult(
                passed=False,
                check_name="referential_integrity",
                severity="error",
                details={
                    "foreign_key": foreign_key_col,
                    "invalid_values": list(invalid)[:10],
                    "invalid_count": len(invalid)
                },
                recommendation="Reconcile keys or update reference data"
            )
        
        return ValidationResult(
            passed=True,
            check_name="referential_integrity",
            severity="info",
            details={"foreign_key": foreign_key_col, "valid_references": len(reference_values)}
        )
    
    # Run complete validation suite
    def run_full_validation(
        self,
        df: DataFrame,
        schema_config: Dict[str, Any]
    ) -> Dict[str, List[ValidationResult]]:
        results = {
            "schema": [],
            "nulls": [],
            "duplicates": [],
            "referential": [],
            "summary": {"passed": 0, "failed": 0, "warnings": 0}
        }
        
        # Schema validation
        schema_result = self.validate_schema(
            df,
            schema_config.get("required_columns", []),
            schema_config.get("column_types", {})
        )
        results["schema"].append(schema_result)
        self._update_summary(results["summary"], schema_result)
        
        # Null validation
        null_results = self.validate_nulls(
            df,
            schema_config.get("numeric_columns", []),
            schema_config.get("categorical_columns", [])
        )
        results["nulls"].extend(null_results)
        for r in null_results:
            self._update_summary(results["summary"], r)
        
        # Duplicate validation
        if "composite_key" in schema_config:
            dup_result = self.validate_duplicates(df, schema_config["composite_key"])
            results["duplicates"].append(dup_result)
            self._update_summary(results["summary"], dup_result)
        
        # Referential integrity
        for fk_config in schema_config.get("foreign_keys", []):
            fk_result = self.validate_referential_integrity(
                df,
                fk_config["column"],
                set(fk_config["reference_values"])
            )
            results["referential"].append(fk_result)
            self._update_summary(results["summary"], fk_result)
        
        logger.info(
            "validation_complete",
            passed=results["summary"]["passed"],
            failed=results["summary"]["failed"],
            warnings=results["summary"]["warnings"]
        )
        
        return results
    
    # Update validation summary counters
    @staticmethod
    def _update_summary(summary: Dict, result: ValidationResult) -> None:
        if result.severity == "error" and not result.passed:
            summary["failed"] += 1
        elif result.severity == "warning" and not result.passed:
            summary["warnings"] += 1
        else:
            summary["passed"] += 1