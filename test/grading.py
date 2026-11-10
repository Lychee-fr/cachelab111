"""Part B 性能分的计分规则。

权重与满分线只在这里定义，README.md 中 Part B “测试与分数”一节需要与之保持一致。

综合加速比 W = sum(WEIGHTS[i] * 第 i 个 case 的加速比)：
    W <= ZERO_SPEEDUP   得分率 0
    W >= FULL_SPEEDUP   得分率 1
    其间按 W 线性插值
按综合加速比计分，各个 case 之间可以互相弥补，不对单个 case 单独设满分线。
"""

# 下标依次对应 case0, case1, case2, case3
WEIGHTS = [0.0, 0.3, 0.3, 0.4]  # case0 只用于演示，不计分
ZERO_SPEEDUP = 1.0  # 综合加速比为 1（与 baseline 持平或更差）得 0 分
FULL_SPEEDUP = 8.0  # 综合加速比达到该值得满分，超过不再加分


def weighted_speedup(speedups: list) -> float:
    """综合加速比。speedups 依次为 case0 ~ case3 的加速比。"""
    return sum(w * s for w, s in zip(WEIGHTS, speedups))


def perf_rate(speedups: list) -> float:
    """Part B 性能得分率，范围 [0, 1]。speedups 依次为 case0 ~ case3 的加速比。"""
    rate = (weighted_speedup(speedups) - ZERO_SPEEDUP) / (FULL_SPEEDUP - ZERO_SPEEDUP)
    return min(1.0, max(0.0, rate))


def speedups_from_results(results: list) -> list:
    """从 gemm_test.test_gemm() 的返回值还原 case0 ~ case3 的加速比。

    返回值依次是 case0 ~ case3 各 4 项 (miss_cache, miss_reg, latency, baseline)，
    最后一项是综合加速比。失败 case 的前三项为 -1，其加速比为 0。
    """
    return [
        results[4 * i + 3] / results[4 * i + 2]
        if results[4 * i + 2] > 0 else 0.0
        for i in range(4)
    ]
