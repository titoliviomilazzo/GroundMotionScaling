#!/usr/bin/env python3
"""
make_figures.py — README용 그림 생성 스크립트

생성물 (assets/):
  1. design_spectrum.png   : KDS vs IBC 설계 응답스펙트럼 비교
  2. ground_motions.png    : 예제 지진파 가속도 시간이력 (3종)
  3. scaling_overview.png  : 예제 CSV 기반 지진파별 스케일팩터

실행:
  python tools/make_figures.py
"""

import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 저장소 루트를 import 경로에 추가 (scaler 모듈 사용)
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scaler import GroundMotionScaler  # noqa: E402

ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

# 한글 폰트 (Windows). 없으면 기본 폰트로 안전하게 폴백.
for _f in ("Malgun Gothic", "AppleGothic", "NanumGothic", "DejaVu Sans"):
    try:
        matplotlib.rcParams["font.family"] = _f
        break
    except Exception:
        continue
matplotlib.rcParams["axes.unicode_minus"] = False

ACCENT = "#1f6feb"
ACCENT2 = "#d1242f"


def fig_design_spectrum():
    """KDS / IBC 설계 응답스펙트럼 비교 곡선."""
    periods = np.linspace(0.01, 4.0, 400)
    target_pga = 0.22

    kds = GroundMotionScaler(code="KDS", target_pga=target_pga)
    ibc = GroundMotionScaler(code="IBC", target_pga=target_pga)
    sa_kds = [kds.design_spectrum(t) for t in periods]
    sa_ibc = [ibc.design_spectrum(t) for t in periods]

    fig, ax = plt.subplots(figsize=(8, 4.6), dpi=130)
    ax.plot(periods, sa_kds, color=ACCENT, lw=2.4, label="KDS 41 17 (간이)")
    ax.plot(periods, sa_ibc, color=ACCENT2, lw=2.0, ls="--", label="IBC 2021 (간이)")

    # 기본 주기 격자점 표시
    marks = [0.2, 0.5, 1.0, 2.0, 3.0]
    ax.scatter(marks, [kds.design_spectrum(t) for t in marks],
               color=ACCENT, zorder=5, s=45, edgecolor="white", linewidth=1.2)

    ax.set_title(f"설계 응답스펙트럼  (목표 PGA = {target_pga} g, 감쇠비 5%)",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("주기 Period  T (s)")
    ax.set_ylabel("스펙트럼 가속도  Sa (g)")
    ax.grid(True, alpha=0.3)
    ax.legend(frameon=False)
    ax.set_xlim(0, 4)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    out = ASSETS / "design_spectrum.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"saved {out}")


def _read_txt(path: Path):
    """clean된 지진파 TXT (1행=이름, 이후 'time accel') 읽기."""
    lines = path.read_text(encoding="utf-8").splitlines()
    name = lines[0].strip()
    t, a = [], []
    for ln in lines[1:]:
        p = ln.split()
        if len(p) >= 2:
            try:
                t.append(float(p[0])); a.append(float(p[1]))
            except ValueError:
                continue
    return name, np.array(t), np.array(a)


def fig_ground_motions():
    """예제 지진파 가속도 시간이력 3종."""
    txt_dir = ROOT / "examples" / "txt"
    files = sorted(txt_dir.glob("*.txt"))[:3]
    if not files:
        print("no example txt found, skip ground_motions.png")
        return

    fig, axes = plt.subplots(len(files), 1, figsize=(8, 5.4), dpi=130, sharex=False)
    if len(files) == 1:
        axes = [axes]
    for ax, fp in zip(axes, files):
        name, t, a = _read_txt(fp)
        ax.plot(t, a, color=ACCENT, lw=0.7)
        pk = float(np.max(np.abs(a))) if a.size else 0.0
        ax.set_title(f"{fp.stem}   (peak |a| = {pk:.4f})", fontsize=10, loc="left")
        ax.grid(True, alpha=0.25)
        ax.set_ylabel("a")
        ax.margins(x=0)
    axes[-1].set_xlabel("시간 Time (s)")
    fig.suptitle("예제 지진파 가속도 시간이력", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out = ASSETS / "ground_motions.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"saved {out}")


def fig_scaling_overview():
    """예제 CSV 기반 지진파별 평균 스케일팩터."""
    csv_path = ROOT / "examples" / "example_gm.csv"
    target_pga = 0.22
    scaler = GroundMotionScaler(code="KDS", target_pga=target_pga)
    factors, _ = scaler.scale_from_csv(str(csv_path))

    names = list(factors.keys())
    avg = [factors[n]["avg_scale"] for n in names]

    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=130)
    bars = ax.bar(names, avg, color=ACCENT, alpha=0.9, edgecolor="white")
    ax.axhline(1.0, color="#888", lw=1, ls=":")
    for b, v in zip(bars, avg):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.03, f"{v:.2f}",
                ha="center", va="bottom", fontsize=9)
    ax.set_title(f"지진파별 평균 스케일팩터  (목표 PGA = {target_pga} g)",
                 fontsize=13, fontweight="bold")
    ax.set_ylabel("평균 스케일팩터  (×)")
    ax.set_ylim(0, max(avg) * 1.25)
    plt.setp(ax.get_xticklabels(), rotation=18, ha="right", fontsize=9)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    out = ASSETS / "scaling_overview.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"saved {out}")


if __name__ == "__main__":
    fig_design_spectrum()
    fig_ground_motions()
    fig_scaling_overview()
    print("done.")
