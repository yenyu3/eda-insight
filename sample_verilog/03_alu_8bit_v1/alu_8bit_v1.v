module alu_8bit_v1(
    input        clk,
    input        rst_n,
    input  [7:0] a,
    input  [7:0] b,
    input  [2:0] op,
    output reg [7:0] result,
    output reg       zero,
    output reg       carry
);
    reg [8:0] alu_tmp;

    always @(*) begin
        case (op)
            3'b000: alu_tmp = a + b;
            3'b001: alu_tmp = a - b;
            3'b010: alu_tmp = a & b;
            3'b011: alu_tmp = a | b;
            3'b100: alu_tmp = a ^ b;
            3'b101: alu_tmp = ~a;
            3'b110: alu_tmp = a << 1;
            3'b111: alu_tmp = a >> 1;
            default: alu_tmp = 9'd0;
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            result <= 8'd0;
            zero   <= 1'b1;
            carry  <= 1'b0;
        end else begin
            result <= alu_tmp[7:0];
            carry  <= alu_tmp[8];
            zero   <= (alu_tmp[7:0] == 8'd0);
        end
    end
endmodule
