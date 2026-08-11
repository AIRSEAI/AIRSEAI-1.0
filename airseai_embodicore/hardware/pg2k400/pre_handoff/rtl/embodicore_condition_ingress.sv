`timescale 1ns/1ps

module embodicore_condition_ingress #(
    // 256 FP16 condition values = 4096 bits = 512 bytes.
    parameter integer CONDITION_ELEMS = 256,
    parameter integer ELEM_W = 16,

    // Generic external-memory datapath width.
    parameter integer BUS_W = 128,

    // 0 = denoise-local
    // 1 = policy-local
    // 2 = episode-local (illegal negative control)
    parameter integer CONDITION_LIFETIME = 1
)(
    input  wire clk,
    input  wire rst_n,

    input  wire episode_reset,
    input  wire policy_start,
    input  wire denoise_start,

    output reg  busy,
    output reg  condition_valid,

    output reg [63:0] load_count,
    output reg [63:0] beat_count,
    output reg [63:0] stall_cycles
);

localparam integer CONDITION_BITS =
    CONDITION_ELEMS * ELEM_W;

localparam integer BEATS_PER_LOAD =
    (CONDITION_BITS + BUS_W - 1) / BUS_W;

integer beats_remaining;

wire request_load =
    (CONDITION_LIFETIME == 0)
        ? denoise_start
        : (CONDITION_LIFETIME == 1)
            ? policy_start
            : (policy_start && !condition_valid);

always @(posedge clk) begin
    if (!rst_n) begin
        busy            <= 1'b0;
        condition_valid <= 1'b0;

        load_count      <= 0;
        beat_count      <= 0;
        stall_cycles    <= 0;

        beats_remaining <= 0;
    end
    else begin

        if (episode_reset) begin
            condition_valid <= 1'b0;
        end

        // One memory beat is transferred per busy cycle.
        if (busy) begin
            beat_count   <= beat_count + 1;
            stall_cycles <= stall_cycles + 1;

            if (beats_remaining == 1) begin
                busy             <= 1'b0;
                beats_remaining  <= 0;
                condition_valid  <= 1'b1;
            end
            else begin
                beats_remaining <=
                    beats_remaining - 1;
            end
        end

        // New condition fill.
        if (!busy && request_load) begin
            busy            <= 1'b1;
            load_count      <= load_count + 1;
            beats_remaining <= BEATS_PER_LOAD;
        end
    end
end

endmodule
