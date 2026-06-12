// Compare sample V1: counter-based pulse stretcher.
// When pulse_in is asserted for one clock, pulse_out stays high for WIDTH cycles.
module pulse_stretcher_v1 #(
    parameter WIDTH = 4
) (
    input clk,
    input reset,
    input pulse_in,
    output reg pulse_out
);

reg [$clog2(WIDTH + 1)-1:0] remaining;

always @(posedge clk) begin
    if (reset) begin
        remaining <= 0;
        pulse_out <= 1'b0;
    end else if (pulse_in) begin
        remaining <= WIDTH - 1;
        pulse_out <= 1'b1;
    end else if (remaining != 0) begin
        remaining <= remaining - 1'b1;
        pulse_out <= 1'b1;
    end else begin
        pulse_out <= 1'b0;
    end
end

endmodule
