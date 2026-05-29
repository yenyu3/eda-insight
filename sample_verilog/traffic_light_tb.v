module traffic_light_tb;
    reg        clk, rst;
    reg  [3:0] phase_len;
    wire       red, yellow, green;

    traffic_light uut (
        .clk(clk), .rst(rst),
        .phase_len(phase_len),
        .red(red), .yellow(yellow), .green(green)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    initial begin
        $dumpfile("traffic_light.vcd");
        $dumpvars(0, traffic_light_tb);

        rst = 1; phase_len = 4'd5;
        #20 rst = 0;

        // Observe 3 full RED->GREEN->YELLOW cycles
        // Each cycle: 5 + 5 + 3 = 13 clock periods = 130 ns
        // 3 cycles = ~390 ns; add margin
        #500;

        // Change phase_len mid-run to test reconfigurability
        phase_len = 4'd8;
        #300;

        $finish;
    end
endmodule
