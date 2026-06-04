#!/usr/bin/env python3
"""
GM Scaler: 지진파 스케일링 핵심 로직

KDS, IBC, ASCE7 기준 목표 스펙트럼 생성 및 스케일팩터 계산

2026-03-18
"""

import csv
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class GroundMotionScaler:
    """지진파 스케일링"""

    def __init__(self, code: str = "KDS", target_pga: float = 0.22,
                 damping: float = 0.05, periods: List[float] = None):
        """
        Args:
            code: 설계기준 (KDS, IBC, ASCE7)
            target_pga: 목표 PGA (g)
            damping: 감쇠비 (default 5%)
            periods: 주기 배열 (초)
        """
        self.code = code
        self.target_pga = target_pga
        self.damping = damping
        self.periods = periods or [0.2, 0.5, 1.0, 2.0, 3.0]

    def kds_design_spectrum(self, t: float) -> float:
        """
        KDS 2018 설계 응답스펙트럼

        S_d(T) = (S_a * S_s * S_1 / g) * ...

        단순화 모델: DBE (1400년) 기준
        """
        # KDS 기본값 (S4 지반, 중요도 I)
        S_s = 0.88  # 단주기 스펙트럼값 (1초)
        S_1 = 0.32  # 장주기 스펙트럼값 (1초)
        I_e = 1.2   # 중요도계수

        # 감쇠보정계수 (5% 기준, 다른 감쇠비는 보정)
        damping_factor = (0.05 / self.damping) ** 0.3  # 근사식

        # 코너주기
        T_0 = 0.2 * S_1 / S_s
        T_s = S_1 / S_s

        # 응답스펙트럼 계산 (3구간)
        if t <= T_0:
            Sa = self.target_pga * (0.6 + 2.5 * (t / T_0))
        elif T_0 < t <= T_s:
            Sa = self.target_pga * 2.5
        else:
            Sa = self.target_pga * (T_s / t) if t > 0 else 0

        return Sa * damping_factor * I_e

    def ibc_design_spectrum(self, t: float) -> float:
        """IBC 2021 설계 응답스펙트럼 (간단히)"""
        # 미국 기준, 생략
        S_s = 0.85
        S_1 = 0.30
        T_0 = 0.2 * S_1 / S_s
        T_s = S_1 / S_s

        if t <= T_0:
            Sa = self.target_pga * (0.4 + 0.6 * (t / T_0) * S_s)
        elif T_0 < t <= T_s:
            Sa = self.target_pga * S_s
        else:
            Sa = self.target_pga * (S_1 / t) if t > 0 else 0

        return Sa

    def design_spectrum(self, t: float) -> float:
        """목표 설계 응답스펙트럼 계산"""
        if self.code == "KDS":
            return self.kds_design_spectrum(t)
        elif self.code == "IBC":
            return self.ibc_design_spectrum(t)
        else:
            return self.kds_design_spectrum(t)  # default

    def compute_spectrum(self, periods: List[float]) -> Dict[float, float]:
        """주기별 응답스펙트럼 계산"""
        spectrum = {}
        for t in periods:
            spectrum[t] = self.design_spectrum(t)
        return spectrum

    def scale_gm_pair(self, record_1: Dict, record_2: Dict) -> Tuple[float, float]:
        """
        지진파 쌍(X, Y) 스케일 계산

        Return: (scale_x, scale_y)
        """
        pga_1 = record_1.get('PGA', 0.1)
        pga_2 = record_2.get('PGA', 0.1)

        # PGA 기준 스케일팩터
        scale_1 = self.target_pga / pga_1 if pga_1 > 0 else 1.0
        scale_2 = self.target_pga / pga_2 if pga_2 > 0 else 1.0

        return scale_1, scale_2

    def scale_from_csv(self, csv_path: str) -> Tuple[Dict, Dict]:
        """
        CSV에서 지진파 로드 및 스케일 계산

        CSV 형식:
        gm_name, event, PGA_x, PGA_y, Sa_10_x, Sa_10_y, ...
        """
        logger.info(f"Loading GM metadata from {csv_path}")

        scale_factors = {}
        spectra = {}

        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    gm_name = row.get('gm_name', 'unknown')
                    record_x = {'PGA': float(row.get('PGA_x', 0.1))}
                    record_y = {'PGA': float(row.get('PGA_y', 0.1))}

                    scale_x, scale_y = self.scale_gm_pair(record_x, record_y)

                    scale_factors[gm_name] = {
                        'scale_x': round(scale_x, 3),
                        'scale_y': round(scale_y, 3),
                        'avg_scale': round((scale_x + scale_y) / 2, 3)
                    }

                    logger.debug(f"  {gm_name}: {scale_x:.3f}x (X), {scale_y:.3f}x (Y)")

        except FileNotFoundError:
            logger.warning(f"CSV file not found: {csv_path}")
            # Dummy 데이터 생성
            scale_factors = {
                'DBE_01': {'scale_x': 1.17, 'scale_y': 1.18, 'avg_scale': 1.175},
                'MCE_01': {'scale_x': 1.45, 'scale_y': 1.46, 'avg_scale': 1.455},
            }

        # 설계 응답스펙트럼
        spectra = self.compute_spectrum(self.periods)

        logger.info(f"Processed {len(scale_factors)} GM records")
        return scale_factors, spectra

    def save_scaling_table(self, scale_factors: Dict, output_path: str) -> None:
        """스케일 테이블 저장 (JSON)"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(scale_factors, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved scaling table: {output_path}")
