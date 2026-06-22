`timescale 1ns/1ps

module counter_4bit_tb;
    reg clk;
    reg rst_n;
    reg en;
    wire [3:0] count;

    counter_4bit dut(
        .clk(clk),
        .rst_n(rst_n),
        .en(en),
        .count(count)
    );

    always #5 clk = ~clk;

    initial begin
        $dumpfile("counter_4bit.vcd");
        $dumpvars(0, counter_4bit_tb);

        clk = 0;
        rst_n = 0;
        en = 0;

        #20 rst_n = 1;
        #10 en = 1;
        #80 en = 0;
        #20 en = 1;
        #50 $finish;
    end
endmodule