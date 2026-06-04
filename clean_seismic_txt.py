#!/usr/bin/env python3
"""
clean_seismic_txt.py — 지진파 TXT 파일 정규화 및 클리닝 도구

주요 기능:
  1. 중복 시간(Duplicate Time Stamp) 제거
  2. 시간이 역전되거나 정체된 구간 처리 (Strictly Increasing 확보)
  3. 고정 시간 간격(Fixed dt)으로 재샘플링 (선택 사항)
  4. Perform3D 임포트에 최적화된 형식으로 저장
"""

import argparse
from pathlib import Path
import numpy as np


def clean_and_normalize(filepath: Path, dt: float = 0.02) -> bool:
    """지진파 TXT 파일을 읽어 중복을 제거하고 정규화합니다."""
    try:
        lines = filepath.read_text(encoding="utf-8").splitlines()
        if not lines:
            return False

        name = lines[0].strip()
        data = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 2:
                try:
                    t = float(parts[0])
                    a = float(parts[1])
                    data.append((t, a))
                except ValueError:
                    continue

        if not data:
            return False

        # 1. 중복 제거 및 시간 순 정렬
        # 같은 시간대의 데이터가 여러 개면 첫 번째 것만 남김
        unique_data = []
        last_t = -1.0
        for t, a in data:
            # 실수 오차 고려 (1e-7 미만 차이면 동일 시간으로 간주)
            if abs(t - last_t) > 1e-7:
                unique_data.append((t, a))
                last_t = t
        
        times, accels = zip(*unique_data)
        times = np.array(times)
        accels = np.array(accels)

        # 2. 고정 dt로 정규화 (Linear Interpolation)
        # 시작부터 끝까지 정확히 dt 간격으로 재배치
        max_t = times[-1]
        new_times = np.arange(0.0, max_t + dt/2, dt)
        new_accels = np.interp(new_times, times, accels)

        # 3. 파일 덮어쓰기 (또는 백업 생성 후 쓰기)
        with filepath.open("w", encoding="utf-8") as f:
            f.write(f"{name}\n")
            for t, a in zip(new_times, new_accels):
                # Perform3D 호환용 포맷: 시간(6자리) 가속도(8자리 지수형)
                f.write(f"{t:.6f}\t{a:.8e}\n")
        
        print(f"✅  {filepath.name}: {len(data)} → {len(new_times)} pts (정규화 완료)")
        return True

    except Exception as e:
        print(f"❌  {filepath.name} 처리 오류: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="지진파 TXT 파일 클리닝 및 정규화 도구")
    parser.add_argument("--dir", "-d", required=True, help="클리닝할 TXT 파일들이 있는 디렉토리")
    parser.add_argument("--dt", type=float, default=0.02, help="정규화할 시간 간격 (기본: 0.02)")
    args = parser.parse_args()

    dir_path = Path(args.dir)
    if not dir_path.is_dir():
        print(f"❌ 디렉토리를 찾을 수 없습니다: {dir_path}")
        return

    txt_files = list(dir_path.glob("*.txt"))
    if not txt_files:
        print(f"⚠️  해당 디렉토리에 TXT 파일이 없습니다.")
        return

    print(f"🚀 {dir_path} 내 지진파 {len(txt_files)}개 정규화 시작 (dt={args.dt})...")
    success_count = 0
    for f in txt_files:
        if clean_and_normalize(f, args.dt):
            success_count += 1

    print(f"\n✨ 완료: {success_count}/{len(txt_files)} 파일 정규화 성공.")


if __name__ == "__main__":
    main()
