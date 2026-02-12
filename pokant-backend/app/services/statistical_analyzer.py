"""
Calculate statistical significance for A/B tests.

Uses a two-proportion z-test to determine whether the variant
outperforms the control with sufficient confidence.
"""

from scipy import stats


class StatisticalAnalyzer:
    @staticmethod
    def calculate_significance(
        control_successes: int,
        control_total: int,
        variant_successes: int,
        variant_total: int,
    ) -> dict:
        """
        Two-proportion z-test for A/B test results.

        Returns:
            confidence_level (0-100), p_value, is_significant (p < 0.05),
            min_sample_met (need 30+ per group).
        """
        min_sample_met = control_total >= 30 and variant_total >= 30

        if not min_sample_met:
            return {
                "confidence_level": 0,
                "p_value": 1.0,
                "is_significant": False,
                "min_sample_met": False,
                "z_score": 0,
                "improvement": 0,
                "message": f"Need 30+ calls per group (control={control_total}, variant={variant_total})",
            }

        p1 = control_successes / control_total
        p2 = variant_successes / variant_total

        p_pool = (control_successes + variant_successes) / (
            control_total + variant_total
        )
        se = (
            p_pool * (1 - p_pool) * (1 / control_total + 1 / variant_total)
        ) ** 0.5

        z = (p2 - p1) / se if se > 0 else 0.0
        p_value = 2 * (1 - stats.norm.cdf(abs(z)))
        confidence = (1 - p_value) * 100

        return {
            "confidence_level": round(confidence, 1),
            "p_value": round(p_value, 4),
            "is_significant": p_value < 0.05,
            "min_sample_met": True,
            "z_score": round(z, 2),
            "improvement": round((p2 - p1) * 100, 1),
        }

    @staticmethod
    def project_annual_impact(
        monthly_calls: int,
        improvement_rate: float,
        avg_revenue_per_call: float = 20.0,
    ) -> dict:
        """
        Project revenue impact from the measured improvement.

        Args:
            monthly_calls: Average monthly call volume.
            improvement_rate: Improvement in success rate (e.g. 0.08 for 8pp).
            avg_revenue_per_call: Revenue per successful call.
        """
        additional_monthly = monthly_calls * improvement_rate
        additional_annual = additional_monthly * 12

        return {
            "additional_calls_monthly": int(additional_monthly),
            "additional_calls_annual": int(additional_annual),
            "revenue_monthly": round(additional_monthly * avg_revenue_per_call, 2),
            "revenue_annual": round(additional_annual * avg_revenue_per_call, 2),
        }
