# 本地评测与维护

本目录为课程提供的评测代码，学生请勿修改。在项目根目录运行：

```bash
python3 test/csim_test.py
python3 test/gemm_test.py
python3 test/gemm_test.py --baseline
python3 test/overall_test.py
```

需要 Ubuntu 24.04 x86-64、Python 3、gcc/g++、make，以及仓库附带的可执行文件 `csim-ref`。脚本仅使用 Python 标准库，运行时不需要网络或密钥。学生提交方式见[README](../README.md#提交)。

- Part A 仅编译 `csim`，使用原有 20 组参数和 trace 与 `csim-ref` 比较；错误或运行失败的测试点不计分。
- Part B 仅编译 `printTrace`，保留原有基本合法性检查、正确性检查、输入矩阵不变检查和 36 个寄存器限制。由 `csim-ref` 统计缓存行为，不依赖学生的 `csim`。
- 每个测试进程最多运行 30 秒，超时会终止整个进程组，防止死循环让评测一直等待。编译时限为 120 秒。
- Part B 某个 case 运行错误或超时时，状态为 `ERROR`，加速比为 0，其余 case 继续。错误 case 没有有效测量数据，表格显示 `N/A`。
- 编译/基本合法性检查失败、参考程序缺失或 baseline 失败时，评测报错退出。自动检查不能覆盖所有实现要求，助教仍需检查源代码。
- 退出码 0 表示评测流程完成，应另外查看 case 状态与分数；退出码 1 表示评测本身未完成。

`grading.py` 统一定义 Part B 权重与得分率。默认满分线为综合加速比 8，百分制性能分为 `100 * 得分率`，实际 Part B 性能分为 `40 * 得分率`。报告和代码风格由助教人工评分。

`overall_test.py` 依次输出 Part A 和 Part B 的报告，两个部分均采用百分制，不另外输出折算分或总分。它还会写入 `.overall_results`：第一行是 Part A 的通过数量和百分制分数；第二行是 case0 至 case3 各四项 `(miss_cache, miss_reg, latency, baseline)`，最后一项为综合加速比。失败 case 的前三项为 `-1`，其加速比按 0 处理。脚本开始时清除旧结果，评测完成后再写入，避免把上次结果误当成本次成绩。

评测使用共享的 trace 和结果路径，请勿在同一目录同时运行多个评测进程。复测不同学生时，每人使用一份新的模板副本，只替换该学生的两份源代码。

## 助教回归检查

```bash
python3 -m unittest discover -s test -p 'test_local_grading.py' -v
bash test/test.sh
```

回归检查在临时副本里构造正确、错误和缺失依赖等情况，验证评测器行为，不会替学生实现实验。`test.sh` 检查原有的四份合法性示例。

旧版的上传脚本、自动上传参数、`--no_linux`、`--disable_auto_make` 和两个 `*_test2.py` 入口已移除。请使用上面的本地入口。旧 `.access_key`、`.last_submit_time` 文件不会被读取；它们仍被 Git 忽略，避免升级旧目录时误提交历史凭据。
