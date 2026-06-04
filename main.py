#!/usr/bin/env python3
"""
GM-Scaling CLI: 지진파 스케일링 도구

KDS 기준 지진파 정규화 및 스케일링 자동화

사용:
    python main.py \
        --input gm_input.csv \
        --target-pga 0.22 \
        --code KDS \
        --output results/

2026-03-18
"""

import argparse
import logging
from pathlib import Path
from scaler import GroundMotionScaler
from report import ReportGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Ground Motion Scaling CLI for Seismic Analysis"
    )

    parser.add_argument(
        "--input", "-i",
        type=str,
        required=True,
        help="Input CSV with ground motion metadata"
    )
    parser.add_argument(
        "--target-pga",
        type=float,
        required=True,
        help="Target PGA (g) for scaling"
    )
    parser.add_argument(
        "--code",
        type=str,
        default="KDS",
        choices=["KDS", "IBC", "ASCE7"],
        help="Design code for target spectrum"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="gm_scaled/",
        help="Output directory for results"
    )
    parser.add_argument(
        "--damping",
        type=float,
        default=0.05,
        help="Damping ratio (default: 5%)"
    )
    parser.add_argument(
        "--periods",
        type=str,
        default="0.2,0.5,1.0,2.0,3.0",
        help="Comma-separated period values for spectrum"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    # 출력 디렉토리 생성
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"GM-Scaling CLI initialized")
    logger.info(f"Input: {args.input}")
    logger.info(f"Target PGA: {args.target_pga} g")
    logger.info(f"Code: {args.code}")
    logger.info(f"Output: {output_dir}")

    try:
        # 지진파 로드 및 스케일
        scaler = GroundMotionScaler(
            code=args.code,
            target_pga=args.target_pga,
            damping=args.damping,
            periods=[float(p) for p in args.periods.split(',')]
        )

        scale_factors, spectra = scaler.scale_from_csv(args.input)

        logger.info(f"✅ Scaling complete: {len(scale_factors)} records")

        # 보고서 생성
        report_gen = ReportGenerator(output_dir=output_dir)
        report_gen.generate_report(
            scale_factors=scale_factors,
            spectra=spectra,
            target_pga=args.target_pga,
            code=args.code
        )

        logger.info(f"✅ Report generated: {output_dir / 'scaling_report.md'}")

    except Exception as e:
        logger.error(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
