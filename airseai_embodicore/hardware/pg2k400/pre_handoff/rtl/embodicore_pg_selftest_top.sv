`timescale 1ns/1ps

module embodicore_pg_selftest_top (
    input  wire clk_50m,
    input  wire reset_n,
    output reg  pass_led
);

localparam integer N_POLICY  = 900;
localparam integer N_DENOISE = 10;

// ------------------------------------------------------------
// Events
// ------------------------------------------------------------

reg episode_reset;
reg policy_start;
reg observation_update;
reg denoise_start;
reg scan_start;

// ------------------------------------------------------------
// Exact EmbodiCore-759 semantic controller
// ------------------------------------------------------------

wire condition_load;
wire scan_reset;
wire condition_valid;
wire scan_state_valid;

embodicore_semantic_controller #(
    .CONDITION_LIFETIME(1),
    .SCAN_LIFETIME(0)
) semantic_ctrl (
    .clk(clk_50m),
    .rst_n(reset_n),

    .episode_reset(episode_reset),
    .policy_start(policy_start),
    .observation_update(observation_update),
    .denoise_start(denoise_start),
    .scan_start(scan_start),

    .condition_load(condition_load),
    .scan_reset(scan_reset),

    .condition_valid(condition_valid),
    .scan_state_valid(scan_state_valid)
);

// ------------------------------------------------------------
// Exact 128-bit portable condition-ingress engine.
// 256 FP16 values = 512 B = 32 beats/load.
// ------------------------------------------------------------

wire ingress_busy;
wire ingress_condition_valid;

wire [63:0] ingress_load_count;
wire [63:0] ingress_beat_count;
wire [63:0] ingress_stall_cycles;

embodicore_condition_ingress #(
    .CONDITION_ELEMS(256),
    .ELEM_W(16),
    .BUS_W(128),
    .CONDITION_LIFETIME(1)
) ingress (
    .clk(clk_50m),
    .rst_n(reset_n),

    .episode_reset(episode_reset),
    .policy_start(policy_start),
    .denoise_start(denoise_start),

    .busy(ingress_busy),
    .condition_valid(ingress_condition_valid),

    .load_count(ingress_load_count),
    .beat_count(ingress_beat_count),
    .stall_cycles(ingress_stall_cycles)
);

// ------------------------------------------------------------
// Count exact semantic events observed from generated RTL.
// ------------------------------------------------------------

reg [31:0] observed_condition_loads;
reg [31:0] observed_scan_resets;

always @(posedge clk_50m) begin
    if (!reset_n) begin
        observed_condition_loads <= 0;
        observed_scan_resets     <= 0;
    end
    else begin
        if (condition_load)
            observed_condition_loads <=
                observed_condition_loads + 1;

        if (scan_reset)
            observed_scan_resets <=
                observed_scan_resets + 1;
    end
end

// ------------------------------------------------------------
// Self-test FSM
// ------------------------------------------------------------

localparam [3:0]
    S_EPISODE     = 4'd0,
    S_EP_GAP      = 4'd1,
    S_POLICY      = 4'd2,
    S_WAIT_COND   = 4'd3,
    S_DENOISE     = 4'd4,
    S_DENOISE_GAP = 4'd5,
    S_DRAIN1      = 4'd6,
    S_DRAIN2      = 4'd7,
    S_CHECK       = 4'd8,
    S_DONE        = 4'd9;

reg [3:0] state;

reg [9:0] policy_idx;
reg [3:0] denoise_idx;

wire done_internal =
    (state == S_DONE);

always @(*) begin
    episode_reset     = 1'b0;
    policy_start      = 1'b0;
    observation_update = 1'b0;
    denoise_start     = 1'b0;
    scan_start        = 1'b0;

    case (state)

        S_EPISODE: begin
            episode_reset = 1'b1;
        end

        S_POLICY: begin
            policy_start       = 1'b1;
            observation_update = 1'b1;
        end

        S_DENOISE: begin
            denoise_start = 1'b1;
            scan_start    = 1'b1;
        end

        default: begin
        end
    endcase
end

always @(posedge clk_50m) begin

    if (!reset_n) begin
        state       <= S_EPISODE;
        policy_idx  <= 0;
        denoise_idx <= 0;
        pass_led    <= 1'b0;
    end

    else begin

        case (state)

            S_EPISODE:
                state <= S_EP_GAP;

            S_EP_GAP:
                state <= S_POLICY;

            S_POLICY:
                state <= S_WAIT_COND;

            // Wait until the complete 512-byte condition
            // has traversed the 128-bit generic ingress.
            S_WAIT_COND: begin
                if (!ingress_busy &&
                    ingress_condition_valid)
                    state <= S_DENOISE;
            end

            S_DENOISE:
                state <= S_DENOISE_GAP;

            S_DENOISE_GAP: begin

                if (denoise_idx == N_DENOISE-1) begin

                    denoise_idx <= 0;

                    if (policy_idx == N_POLICY-1) begin
                        state <= S_DRAIN1;
                    end
                    else begin
                        policy_idx <= policy_idx + 1;
                        state <= S_POLICY;
                    end

                end
                else begin
                    denoise_idx <= denoise_idx + 1;
                    state <= S_DENOISE;
                end
            end

            // Drain delayed registered event outputs.
            S_DRAIN1:
                state <= S_DRAIN2;

            S_DRAIN2:
                state <= S_CHECK;

            S_CHECK: begin

                if (
                    observed_condition_loads == 900 &&
                    observed_scan_resets     == 9000 &&
                    ingress_load_count       == 900 &&
                    ingress_beat_count       == 28800 &&
                    ingress_stall_cycles     == 28800
                )
                    pass_led <= 1'b1;
                else
                    pass_led <= 1'b0;

                state <= S_DONE;
            end

            S_DONE:
                state <= S_DONE;

            default:
                state <= S_EPISODE;

        endcase
    end
end

endmodule
