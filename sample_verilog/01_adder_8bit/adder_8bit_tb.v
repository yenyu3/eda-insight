`timescale 1ns/1ps

module adder_8bit_tb;
    reg  [7:0] a;
    reg  [7:0] b;
    reg        cin;
    wire [7:0] sum;
    wire       cout;

    adder_8bit dut(
        .a(a),
        .b(b),
        .cin(cin),
        .sum(sum),
        .cout(cout)
    );

    initial begin
        $dumpfile("adder_8bit.vcd");
        $dumpvars(0, adder_8bit_tb);

        a = 8'd10; b = 8'd20; cin = 0; #10;
        a = 8'd200; b = 8'd100; cin = 0; #10;
        a = 8'd255; b = 8'd1; cin = 1; #10;
        $finish;
    end
endmodule
