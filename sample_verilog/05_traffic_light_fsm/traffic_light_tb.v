`timescale 1ns/1ps

module traffic_light_tb;
    reg clk;
    reg rst_n;
    reg [3:0] phase_len;
    wire red;
    wire yellow;
    wire green;

    traffic_light dut(
        .clk(clk),
        .rst_n(rst_n),
        .phase_len(phase_len),
        .red(red),
        .yellow(yellow),
        .green(green)
    );

    always #5 clk = ~clk;

    initial begin
        $dumpfile("traffic_light.vcd");
        $dumpvars(0, traffic_light_tb);

        clk = 0;
        rst_n = 0;
        phase_len = 4'd5;

        #20 rst_n = 1;
        #200 phase_len = 4'd8;
        #250 $finish;
    end
endmodule
