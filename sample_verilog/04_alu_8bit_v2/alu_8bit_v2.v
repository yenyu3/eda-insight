module alu_8bit_v2(
    input        clk,
    input        rst_n,
    input  [7:0] a,
    input  [7:0] b,
    input  [2:0] op,
    output reg [7:0] result,
    output reg       zero,
    output reg       carry
);
    reg [8:0] next_value;
    reg [7:0] logic_value;

    always @(*) begin
        case (op)
            3'b000: next_value = a + b;
            3'b001: next_value = a - b;
            3'b010: next_value = {1'b0, (a & b)};
            3'b011: next_value = {1'b0, (a | b)};
            3'b100: next_value = {1'b0, (a ^ b)};
            3'b101: next_value = {1'b0, (~a)};
            3'b110: next_value = {1'b0, (a << 1)};
            3'b111: next_value = {1'b0, (a >> 1)};
            default: next_value = 9'd0;
        endcase

        logic_value = next_value[7:0];
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            result <= 8'd0;
            zero   <= 1'b1;
            carry  <= 1'b0;
        end else begin
            result <= logic_value;
            carry  <= next_value[8];
            zero   <= (logic_value == 8'd0);
        end
    end
endmodule
