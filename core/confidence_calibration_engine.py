"""Research-safe empirical calibration for immutable decision confidence scores."""

from dataclasses import dataclass
from enum import Enum
from statistics import mean


CONFIDENCE_BUCKETS = ("50-59", "60-69", "70-79", "80-89", "90-100")


class ConfidenceReliability(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class ConfidenceCalibration:
    raw_score: float
    calibrated_confidence: float
    historical_win_probability: float | None
    confidence_band: str
    sample_size: int
    confidence_reliability: ConfidenceReliability
    calibration_method: str
    calibration_bucket: str
    calibration_warning: str | None
    human_readable_summary: str


@dataclass(frozen=True)
class ConfidenceBucketCalibration:
    calibration_bucket: str
    sample_size: int
    wins: int
    losses: int
    breakeven: int
    average_raw_score: float
    historical_win_probability: float | None
    calibrated_confidence: float | None
    confidence_reliability: ConfidenceReliability
    calibration_method: str
    calibration_warning: str | None


@dataclass(frozen=True)
class AggregateConfidenceCalibrationSummary:
    total_samples: int
    populated_buckets: int
    average_raw_score: float
    average_calibrated_confidence: float
    calibration_method: str
    overall_reliability: ConfidenceReliability
    identity_fallback_buckets: tuple[str, ...]
    human_readable_summary: str


class ConfidenceCalibrationEngine:
    """Calibrate confidence for reporting without changing authoritative scores."""

    def calibrate(
        self,
        raw_score: float,
        bucket_calibrations: tuple[ConfidenceBucketCalibration, ...] = (),
    ) -> ConfidenceCalibration:
        raw = max(0.0, min(100.0, float(raw_score)))
        bucket = confidence_bucket(raw)
        historical = next(
            (
                item for item in bucket_calibrations
                if item.calibration_bucket == bucket
            ),
            None,
        )
        if historical is None or historical.sample_size == 0:
            return ConfidenceCalibration(
                raw_score=round(raw, 3),
                calibrated_confidence=round(raw, 3),
                historical_win_probability=None,
                confidence_band=bucket,
                sample_size=0,
                confidence_reliability=ConfidenceReliability.INSUFFICIENT,
                calibration_method="identity",
                calibration_bucket=bucket,
                calibration_warning="No historical outcomes are available for this confidence bucket.",
                human_readable_summary=(
                    f"Raw confidence remains {raw:.1f}/100 because no historical "
                    f"calibration sample exists for bucket {bucket}."
                ),
            )
        calibrated = (
            historical.historical_win_probability
            if historical.sample_size >= 20
            and historical.historical_win_probability is not None
            else raw
        )
        method = "bucketed_empirical" if historical.sample_size >= 20 else "identity"
        warning = (
            None if historical.sample_size >= 100
            else f"Bucket {bucket} has only {historical.sample_size} trades; calibrated confidence remains provisional."
        )
        return ConfidenceCalibration(
            raw_score=round(raw, 3),
            calibrated_confidence=round(float(calibrated), 3),
            historical_win_probability=historical.historical_win_probability,
            confidence_band=bucket,
            sample_size=historical.sample_size,
            confidence_reliability=historical.confidence_reliability,
            calibration_method=method,
            calibration_bucket=bucket,
            calibration_warning=warning,
            human_readable_summary=(
                f"Raw confidence {raw:.1f}/100 maps to {float(calibrated):.1f}% "
                f"using {method.replace('_', ' ')} with {historical.sample_size} "
                f"historical trades ({historical.confidence_reliability.value} reliability)."
            ),
        )

    def build_buckets(
        self,
        observations: list[tuple[float, str]] | tuple[tuple[float, str], ...],
    ) -> tuple[ConfidenceBucketCalibration, ...]:
        grouped: dict[str, list[tuple[float, str]]] = {
            bucket: [] for bucket in CONFIDENCE_BUCKETS
        }
        for raw_score, outcome in observations:
            bucket = confidence_bucket(raw_score)
            if bucket in grouped:
                grouped[bucket].append((float(raw_score), str(outcome)))
        results = []
        for bucket in CONFIDENCE_BUCKETS:
            records = grouped[bucket]
            wins = sum(outcome == "win" for _, outcome in records)
            losses = sum(outcome == "loss" for _, outcome in records)
            breakeven = sum(outcome == "breakeven" for _, outcome in records)
            sample = len(records)
            probability = round(wins / sample * 100.0, 3) if sample else None
            reliability = reliability_for_sample(sample)
            empirical = sample >= 20
            results.append(
                ConfidenceBucketCalibration(
                    calibration_bucket=bucket,
                    sample_size=sample,
                    wins=wins,
                    losses=losses,
                    breakeven=breakeven,
                    average_raw_score=(
                        round(mean(score for score, _ in records), 3)
                        if records else 0.0
                    ),
                    historical_win_probability=probability,
                    calibrated_confidence=probability if empirical else None,
                    confidence_reliability=reliability,
                    calibration_method="bucketed_empirical" if empirical else "identity",
                    calibration_warning=(
                        None if sample >= 100
                        else "At least 100 trades are required for high reliability."
                        if sample else "No trades are available in this bucket."
                    ),
                )
            )
        return tuple(results)

    def summarize(
        self,
        buckets: tuple[ConfidenceBucketCalibration, ...],
    ) -> AggregateConfidenceCalibrationSummary:
        populated = [item for item in buckets if item.sample_size]
        total = sum(item.sample_size for item in populated)
        average_raw = (
            sum(item.average_raw_score * item.sample_size for item in populated) / total
            if total else 0.0
        )
        average_calibrated = (
            sum(
                (
                    item.calibrated_confidence
                    if item.calibrated_confidence is not None
                    else item.average_raw_score
                )
                * item.sample_size
                for item in populated
            ) / total
            if total else 0.0
        )
        reliability = (
            ConfidenceReliability.HIGH if total >= 100
            else ConfidenceReliability.MEDIUM if total >= 20
            else ConfidenceReliability.LOW if total
            else ConfidenceReliability.INSUFFICIENT
        )
        fallbacks = tuple(
            item.calibration_bucket for item in buckets
            if item.calibration_method == "identity"
        )
        return AggregateConfidenceCalibrationSummary(
            total_samples=total,
            populated_buckets=len(populated),
            average_raw_score=round(average_raw, 3),
            average_calibrated_confidence=round(average_calibrated, 3),
            calibration_method="bucketed_empirical_with_identity_fallback",
            overall_reliability=reliability,
            identity_fallback_buckets=fallbacks,
            human_readable_summary=(
                f"Confidence calibration analyzed {total} completed outcomes across "
                f"{len(populated)} populated buckets with {reliability.value} overall reliability."
            ),
        )


def confidence_bucket(score: float) -> str:
    value = max(0.0, min(100.0, float(score)))
    if value < 50:
        return "below_50"
    if value < 60:
        return "50-59"
    if value < 70:
        return "60-69"
    if value < 80:
        return "70-79"
    if value < 90:
        return "80-89"
    return "90-100"


def reliability_for_sample(sample: int) -> ConfidenceReliability:
    if sample <= 0:
        return ConfidenceReliability.INSUFFICIENT
    if sample < 20:
        return ConfidenceReliability.LOW
    if sample < 100:
        return ConfidenceReliability.MEDIUM
    return ConfidenceReliability.HIGH
