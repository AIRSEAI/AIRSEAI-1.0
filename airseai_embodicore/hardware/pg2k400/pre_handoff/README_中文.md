# AIRSEAI-EmbodiCore：PG2K400 最小硬件验证

## 实验目的

本实验不是进行 FPGA 性能 benchmark。

唯一目的：

**验证已经在 Mac 上冻结并通过仿真的 EmbodiCore portable RTL，
能够在真实 PG2K400 上完成综合、布局布线、时序收敛，并正确执行
冻结的 semantic self-test。**

禁止根据 PG 结果修改 RTL 或实验语义。

---

## 目标器件

PG2K400-6IFFBG676

建议使用当前可用的 Pango Design Suite (PDS)。

---

## 顶层文件

`rtl/embodicore_pg_selftest_top.sv`

同时加入：

- `rtl/embodicore_semantic_controller.sv`
- `rtl/embodicore_condition_ingress.sv`

---

## 需要连接的板级信号

顶层只有三个外部信号：

- `clk_50m`
- `reset_n`
- `pass_led`

请从你们手中的 **PG2K400-FFBG676 DEMO 板官方参考工程/原理图**
复制 PA 侧以下管脚约束：

1. 50 MHz FPGA 全局时钟
2. PA 用户按键作为 reset
3. PA 用户 LED 作为 pass_led

**不要猜管脚号。**

如果参考工程中的按键为高有效，
只需在 top 中对 reset 极性做一层反相；
不得修改任何 semantic controller 逻辑。

---

## PDS 操作

1. 新建工程。
2. Device 选择 `PG2K400-6IFFBG676`。
3. 添加 `rtl/` 下三个 SystemVerilog 文件。
4. Top 设置为 `embodicore_pg_selftest_top`。
5. 加入上述三个板级管脚约束。
6. 对 `clk_50m` 设置 50 MHz（20 ns）时钟约束。
7. 运行 Synthesis。
8. 运行 Place & Route / Implementation。
9. 生成 bitstream。
10. 通过 JTAG 下载到 PA。
11. 按下并释放 reset 按键。
12. 观察 `pass_led`。

---

## PASS 判据

LED 最终保持亮：

`pass_led = 1`

对应 RTL 内部冻结结果：

- condition loads = 900
- scan resets = 9000
- condition ingress loads = 900
- 128-bit condition beats = 28800
- ingress stall cycles = 28800

如果 LED 不亮，实验为 FAIL。

不要修改计数目标使其通过。

---

## 请返回的材料

请把 PDS 工程的 report 文件整体压缩返回，并同时填写：

`results/EXPECTED_RESULTS.json`

至少需要：

- PDS version
- 实际 device
- LUT
- FF
- BRAM
- APM
- clock constraint
- WNS
- timing PASS/FAIL
- board self-test PASS/FAIL

如果 PDS 不直接给出“maximum Fmax”，不要自行估计。
只报告 50 MHz timing constraint 和 WNS 即可。

---

## 重要说明

本实验只验证 EmbodiCore semantic-control / condition-ingress RTL
在真实器件上的物理可实现性。

本实验不用于声称：

- full Mamba accelerator speedup
- full-policy FPGA latency
- FPGA energy improvement
- 90% whole-accelerator speedup

90% 结果仅指已经冻结的 condition-ingress traffic reduction。
