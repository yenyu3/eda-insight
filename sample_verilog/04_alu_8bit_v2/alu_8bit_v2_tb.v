`timescale 1ns/1ps

module alu_8bit_v2_tb;
    reg clk;
    reg rst_n;
    reg [7:0] a;
    reg [7:0] b;
    reg [2:0] op;
    wire [7:0] result;
    wire zero;
    wire carry;

    alu_8bit_v2 dut(
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

    initial begin
        $dumpfile("alu_8bit_v2.vcd");
        $dumpvars(0, alu_8bit_v2_tb);

        clk = 0;
        rst_n = 0;
        a = 0; b = 0; op = 0;

        #12 rst_n = 1;
        #8  a = 8'd10;  b = 8'd20;  op = 3'b000;
        #10 a = 8'd200; b = 8'd100; op = 3'b000;
        #10 a = 8'd50;  b = 8'd20;  op = 3'b001;
        #10 a = 8'hFF;  b = 8'h0F;  op = 3'b010;
        #10 a = 8'hF0;  b = 8'h0F;  op = 3'b011;
        #10 a = 8'hAA;  b = 8'h55;  op = 3'b100;
        #10 a = 8'hAA;  b = 8'h00;  op = 3'b101;
        #10 a = 8'h01;  b = 8'h00;  op = 3'b110;
        #10 a = 8'h80;  b = 8'h00;  op = 3'b111;
        #10 a = 8'd0;   b = 8'd0;   op = 3'b000;

        #20 $finish;
    end
endmodule
