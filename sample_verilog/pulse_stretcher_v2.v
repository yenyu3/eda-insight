// Compare sample V2: shift-register pulse stretcher.
// Same external behavior as V1, but a different implementation style and area profile.
module pulse_stretcher_v2 #(
    parameter WIDTH = 4
) (
    input clk,
    input reset,
    input pulse_in,
    output pulse_out
);

reg [WIDTH-1:0] history;

always @(posedge clk) begin
    if (reset) begin
        history <= {WIDTH{1'b0}};
    end else begin
        history <= {history[WIDTH-2:0], pulse_in};
    end
end

assign pulse_out = |history;

endmodule
