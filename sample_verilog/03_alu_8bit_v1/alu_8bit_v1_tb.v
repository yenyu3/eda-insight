`timescale 1ns/1ps

module alu_8bit_v1_tb;
    reg clk;
    reg rst_n;
    reg [7:0] a;
    reg [7:0] b;
    reg [2:0] op;
    wire [7:0] result;
    wire zero;
    wire carry;

    alu_8bit_v1 dut(
        .clk(clk),
        .rst_n(rst_n),
        .a(a),
        .b(b),
        .op(op),
        .result(result),
        .zero(zero),
        .carry(carry)
    );

    always #5 clk = ~clk;

    task apply_op(input [7:0] ta, input [7:0] tb, input [2:0] top);
    begin
        a = ta; b = tb; op = top;
        #10;
    end
    endtask

    initial begin
        $dumpfile("alu_8bit_v1.vcd");
        $dumpvars(0, alu_8bit_v1_tb);

        clk = 0;
        rst_n = 0;
        a = 0; b = 0; op = 0;

        #12 rst_n = 1;

        apply_op(8'd10,  8'd20,  3'b000);
        apply_op(8'd200, 8'd100, 3'b000);
        apply_op(8'd50,  8'd20,  3'b001);
        apply_op(8'hFF,  8'h0F,  3'b010);
        apply_op(8'hF0,  8'h0F,  3'b011);
        apply_op(8'hAA,  8'h55,  3'b100);
        apply_op(8'hAA,  8'h00,  3'b101);
        apply_op(8'h01,  8'h00,  3'b110);
        apply_op(8'h80,  8'h00,  3'b111);
        apply_op(8'd0,   8'd0,   3'b000);

        #20 $finish;
    end
endmodule
