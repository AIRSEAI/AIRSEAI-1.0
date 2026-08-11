`timescale 1ns/1ps

module tb_pg_selftest;

reg clk_50m = 0;
reg reset_n = 0;

wire pass_led;

always #10 clk_50m = ~clk_50m; // 50 MHz

embodicore_pg_selftest_top dut (
    .clk_50m(clk_50m),
    .reset_n(reset_n),
    .pass_led(pass_led)
);

integer timeout;

initial begin

    repeat (10)
        @(posedge clk_50m);

    reset_n = 1;

    timeout = 0;

    while (!dut.done_internal && timeout < 200000) begin
        @(posedge clk_50m);
        timeout = timeout + 1;
    end

    if (!dut.done_internal) begin
        $display("RESULT timeout=1");
        $display("SELFTEST: FAIL");
        $finish;
    end

    #1;

    $display(
        "RESULT condition_loads=%0d",
        dut.observed_condition_loads
    );

    $display(
        "RESULT scan_resets=%0d",
        dut.observed_scan_resets
    );

    $display(
        "RESULT ingress_loads=%0d",
        dut.ingress_load_count
    );

    $display(
        "RESULT ingress_beats=%0d",
        dut.ingress_beat_count
    );

    $display(
        "RESULT ingress_stall_cycles=%0d",
        dut.ingress_stall_cycles
    );

    $display(
        "RESULT pass_led=%0d",
        pass_led
    );

    if (
        pass_led == 1'b1 &&
        dut.observed_condition_loads == 900 &&
        dut.observed_scan_resets     == 9000 &&
        dut.ingress_load_count       == 900 &&
        dut.ingress_beat_count       == 28800 &&
        dut.ingress_stall_cycles     == 28800
    )
        $display("SELFTEST: PASS");
    else
        $display("SELFTEST: FAIL");

    $finish;
end

endmodule
