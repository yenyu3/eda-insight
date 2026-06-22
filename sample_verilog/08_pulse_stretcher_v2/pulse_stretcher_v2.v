module pulse_stretcher_v2(
    input clk,
    input rst_n,
    input pulse_in,
    output pulse_out
);
    reg [3:0] shift_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            shift_reg <= 4'b0000;
        end else begin
            shift_reg <= {shift_reg[2:0], pulse_in};
        end
    end

    assign pulse_out = |shift_reg;
endmodule
