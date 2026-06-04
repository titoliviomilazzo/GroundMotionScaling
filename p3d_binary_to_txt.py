#!/usr/bin/env python3
"""
p3d_binary_to_txt.py — Perform3D 지진파 바이너리 → TXT 변환기

바이너리 구조 (리버스엔지니어링 확인):
  [0:40]  name     : 40바이트 문자열 (null/space padding)
  [40:42] flag     : uint16 LE (= 1)
  [42:44] npts     : uint16 LE (데이터 포인트 수)
  [44:48] peak_neg : float32 LE (음의 최대 가속도)
  [48:52] peak_pos : float32 LE (양의 최대 가속도)
  [52:56] duration : float32 LE (전체 지속 시간, 초)
  [56 ~ ] data     : npts × (float32 time, float32 accel)

사용:
  # 파일 단위
  python p3d_binary_to_txt.py "test_results/CHi_CHi_EW"

  # 여러 파일
  python p3d_binary_to_txt.py "test_results/CHi_CHi_EW" "test_results/El Centro_EW"

  # 디렉토리 일괄
  python p3d_binary_to_txt.py --dir test_results/

  # 출력 폴더 지정
  python p3d_binary_to_txt.py --dir test_results/ --out txt_output/
"""

import argparse
import struct
from pathlib import Path
import numpy as np


HEADER_SIZE = 56  # bytes
RECORD_SIZE = 8   # (float32 time, float32 accel)


def parse_p3d_binary(filepath: Path) -> dict:
    """Perform3D 바이너리 파일 파싱."""
    data = filepath.read_bytes()

    if len(data) < HEADER_SIZE:
        raise ValueError(f"파일 크기 부족 ({len(data)} bytes < {HEADER_SIZE}): {filepath}")

    name     = data[0:40].rstrip(b"\x00 ").decode("ascii", errors="replace")
    flag     = struct.unpack_from("<H", data, 40)[0]
    npts     = struct.unpack_from("<H", data, 42)[0]
    peak_neg = struct.unpack_from("<f", data, 44)[0]
    peak_pos = struct.unpack_from("<f", data, 48)[0]
    duration = struct.unpack_from("<f", data, 52)[0]

    expected_size = HEADER_SIZE + npts * RECORD_SIZE
    if len(data) != expected_size:
        raise ValueError(
            f"파일 크기 불일치: {len(data)} bytes (예상 {expected_size}, npts={npts})"
        )

    times  = []
    accels = []
    for i in range(npts):
        offset = HEADER_SIZE + i * RECORD_SIZE
        t, a = struct.unpack_from("<ff", data, offset)
        times.append(t)
        accels.append(a)

    dt = duration / (npts - 1) if npts > 1 else 0.0

    return {
        "name":     name,
        "flag":     flag,
        "npts":     npts,
        "peak_neg": peak_neg,
        "peak_pos": peak_pos,
        "duration": duration,
        "dt":       dt,
        "times":    times,
        "accels":   accels,
    }


def clean_record(rec: dict) -> dict:
    """기록의 중복 시간만 제거하고 원본 dt를 유지합니다."""
    times = np.array(rec["times"])
    accels = np.array(rec["accels"])

    # 중복 제거 (Strictly Increasing 확보)
    unique_mask = np.concatenate(([True], np.diff(times) > 1e-8))
    new_times = times[unique_mask]
    new_accels = accels[unique_mask]

    return {
        "name": rec["name"],
        "npts": len(new_times),
        "duration": new_times[-1],
        "dt": rec["dt"],
        "times": new_times,
        "accels": new_accels,
    }


def normalize_record(rec: dict, target_dt: float = 0.02) -> dict:
    """기록을 일정한 dt로 재샘플링(보간)하여 정규화합니다."""
    times = np.array(rec["times"])
    accels = np.array(rec["accels"])

    # 1. 중복 제거 우선
    unique_mask = np.concatenate(([True], np.diff(times) > 1e-8))
    times = times[unique_mask]
    accels = accels[unique_mask]

    # 2. 고정 dt로 재샘플링 (선형 보간)
    duration = times[-1]
    new_times = np.arange(0.0, duration + target_dt/2, target_dt)
    new_accels = np.interp(new_times, times, accels)

    return {
        "name": rec["name"],
        "npts": len(new_times),
        "duration": duration,
        "dt": target_dt,
        "times": new_times,
        "accels": new_accels,
    }


def write_txt(rec: dict, out_path: Path) -> None:
    """파싱 결과를 TXT로 저장."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write(f"{rec['name']}\n")
        for t, a in zip(rec["times"], rec["accels"]):
            f.write(f"{t:.6f}\t{a:.8e}\n")


def convert_file(src: Path, out_base: Path, target_dt: float = 0.02) -> None:
    try:
        rec_raw = parse_p3d_binary(src)
        
        # 1. Native DT 버전 (중복만 제거)
        rec_native = clean_record(rec_raw)
        path_native = out_base / "txt_native_dt" / (src.name + ".txt")
        write_txt(rec_native, path_native)
        
        # 2. 0.02s 정규화 버전
        rec_norm = normalize_record(rec_raw, target_dt)
        path_norm = out_base / "txt_0.02s" / (src.name + ".txt")
        write_txt(rec_norm, path_norm)
        
        print(f"✅  {src.name}:")
        print(f"    - Native : {path_native.name} (dt={rec_native['dt']:.4f}s, {rec_native['npts']} pts)")
        print(f"    - Normal : {path_norm.name} (dt={rec_norm['dt']:.2f}s, {rec_norm['npts']} pts)")
    except Exception as e:
        print(f"❌  {src.name}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Perform3D 지진파 바이너리 → TXT 변환기"
    )
    parser.add_argument(
        "files", nargs="*", type=str,
        help="변환할 바이너리 파일 경로 (복수 가능)"
    )
    parser.add_argument(
        "--dir", "-d", type=str, default=None,
        help="디렉토리 일괄 변환 (확장자 없는 파일 대상)"
    )
    parser.add_argument(
        "--out", "-o", type=str, default=None,
        help="출력 폴더 (기본: 각 입력 파일 폴더의 txt_output)"
    )
    parser.add_argument(
        "--dt", type=float, default=0.02,
        help="정규화할 시간 간격 (기본: 0.02)"
    )
    args = parser.parse_args()

    targets: list[Path] = []

    # 개별 파일
    for fp in args.files:
        p = Path(fp)
        if not p.exists():
            print(f"⚠️  파일 없음: {p}")
            continue
        targets.append(p)

    # 디렉토리 일괄
    if args.dir:
        d = Path(args.dir)
        if not d.is_dir():
            print(f"❌  디렉토리 없음: {d}")
            return
        # 텍스트/메타 파일 제외, 나머지 모두 대상 (K.J_EW 처럼 도트 포함 이름도 처리)
        _SKIP_SUFFIXES = {".txt", ".csv", ".json", ".md", ".py", ".xlsx", ".log"}
        targets += [
            f for f in d.iterdir()
            if f.is_file() and f.suffix.lower() not in _SKIP_SUFFIXES
        ]

    if not targets:
        parser.print_help()
        return

    # 출력 폴더 결정
    if args.out:
        out_base = Path(args.out)
        for src in targets:
            convert_file(src, out_base, args.dt)
        print(f"\n출력 위치: {out_base.resolve()}")
    else:
        out_dirs = set()
        for src in targets:
            per_file_out_dir = src.parent / "txt_output"
            out_dirs.add(per_file_out_dir.resolve())
            convert_file(src, per_file_out_dir, args.dt)

        print("\n출력 위치:")
        for p in sorted(out_dirs):
            print(f"- {p}")


if __name__ == "__main__":
    main()
