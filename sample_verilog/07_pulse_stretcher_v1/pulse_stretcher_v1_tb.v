`timescale 1ns/1ps

module pulse_stretcher_v1_tb;
    reg clk;
    reg rst_n;
    reg pulse_in;
    wire pulse_out;

    pulse_stretcher_v1 dut(
        .clk(clk),
        .rst_n(rst_n),
        .pulse_in(pulse_in),
        .pulse_out(pulse_out)
    );

    always #5 clk = ~clk;

    initial begin
        $dumpfile("pulse_stretcher_v1.vcd");
        $dumpvars(0, pulse_stretcher_v1_tb);

        clk = 0;
        rst_n = 0;
        pulse_in = 0;

        #15 rst_n = 1;
        #20 pulse_in = 1;
        #10 pulse_in = 0;
        #100 pulse_in = 1;
        #10 pulse_in = 0;
        #100 $finish;
    end
endmodule
