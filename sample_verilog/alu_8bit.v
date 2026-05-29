module alu_8bit (
    input        clk,
    input        rst,
    input  [7:0] a,
    input  [7:0] b,
    input  [2:0] op,
    output reg [7:0] result,
    output reg       zero,
    output reg       carry_out
);

localparam OP_ADD = 3'd0;
localparam OP_SUB = 3'd1;
localparam OP_AND = 3'd2;
localparam OP_OR  = 3'd3;
localparam OP_XOR = 3'd4;
localparam OP_NOT = 3'd5;
localparam OP_SHL = 3'd6;
localparam OP_SHR = 3'd7;

reg [8:0] alu_out;

// Combinational computation
always @(*) begin
    case (op)
        OP_ADD: alu_out = {1'b0, a} + {1'b0, b};
        OP_SUB: alu_out = {1'b0, a} - {1'b0, b};
        OP_AND: alu_out = {1'b0, a & b};
        OP_OR:  alu_out = {1'b0, a | b};
        OP_XOR: alu_out = {1'b0, a ^ b};
        OP_NOT: alu_out = {1'b0, ~a};
        OP_SHL: alu_out = {a[7], a[6:0], 1'b0};
        OP_SHR: alu_out = {a[0], 1'b0, a[7:1]};
        default: alu_out = 9'd0;
    endcase
end

// Register outputs on rising edge
always @(posedge clk) begin
    if (rst) begin
        result    <= 8'h00;
        zero      <= 1'b0;
        carry_out <= 1'b0;
    end else begin
        result    <= alu_out[7:0];
        zero      <= (alu_out[7:0] == 8'h00);
        carry_out <= alu_out[8];
    end
end

endmodule
