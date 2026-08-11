`timescale 1ns/1ps

module embodicore_semantic_controller #(
    // 0 = denoise-local condition
    // 1 = policy-local condition
    // 2 = episode-local condition
    parameter integer CONDITION_LIFETIME = 1,

    // 0 = scan-local state
    // 1 = episode-local state
    parameter integer SCAN_LIFETIME = 0
)(
    input  wire clk,
    input  wire rst_n,

    input  wire episode_reset,
    input  wire policy_start,
    input  wire observation_update,
    input  wire denoise_start,
    input  wire scan_start,

    output reg  condition_load,
    output reg  scan_reset,

    output reg  condition_valid,
    output reg  scan_state_valid
);

always @(posedge clk) begin
    if (!rst_n) begin
        condition_load   <= 1'b0;
        scan_reset       <= 1'b0;
        condition_valid  <= 1'b0;
        scan_state_valid <= 1'b0;
    end
    else begin
        condition_load <= 1'b0;
        scan_reset     <= 1'b0;

        // ----------------------------------------------------
        // Episode reset invalidates everything.
        // ----------------------------------------------------
        if (episode_reset) begin
            condition_valid  <= 1'b0;
            scan_state_valid <= 1'b0;
        end

        // ----------------------------------------------------
        // Condition lifetime
        // ----------------------------------------------------

        if (CONDITION_LIFETIME == 0) begin
            // denoise-local:
            // every independent denoise invocation reloads.
            if (denoise_start) begin
                condition_load  <= 1'b1;
                condition_valid <= 1'b1;
            end
        end

        else if (CONDITION_LIFETIME == 1) begin
            // policy-local:
            // new observation invalidates prior condition.
            // load once for the new policy.
            if (policy_start || observation_update) begin
                condition_load  <= 1'b1;
                condition_valid <= 1'b1;
            end
        end

        else begin
            // episode-local:
            // intentionally ignores observation changes.
            // This is the contract-agnostic illegal case.
            if (!condition_valid &&
                (policy_start || denoise_start)) begin
                condition_load  <= 1'b1;
                condition_valid <= 1'b1;
            end
        end

        // ----------------------------------------------------
        // Scan-state lifetime
        // ----------------------------------------------------

        if (SCAN_LIFETIME == 0) begin
            // Every independent scan starts from reset state.
            if (scan_start) begin
                scan_reset       <= 1'b1;
                scan_state_valid <= 1'b1;
            end
        end
        else begin
            // Illegal episode persistence:
            // only initialize when no persistent state exists.
            if (scan_start && !scan_state_valid) begin
                scan_reset       <= 1'b1;
                scan_state_valid <= 1'b1;
            end
        end
    end
end

endmodule
