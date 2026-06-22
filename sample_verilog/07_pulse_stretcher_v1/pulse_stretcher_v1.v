module pulse_stretcher_v1(
    input clk,
    input rst_n,
    input pulse_in,
    output reg pulse_out
);
    reg [1:0] cnt;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cnt <= 2'd0;
            pulse_out <= 1'b0;
        end else begin
            if (pulse_in) begin
                cnt <= 2'd3;
                pulse_out <= 1'b1;
            end else if (cnt != 2'd0) begin
                cnt <= cnt - 2'd1;
                pulse_out <= 1'b1;
            end else begin
                pulse_out <= 1'b0;
            end
        end
    end
endmodule
