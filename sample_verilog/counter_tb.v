module counter_tb;
    reg clk, reset, enable;
    wire [3:0] count;

    counter_4bit uut (
        .clk(clk),
        .reset(reset),
        .enable(enable),
        .count(count)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    initial begin
        $dumpfile("counter.vcd");
        $dumpvars(0, counter_tb);
        reset = 1; enable = 0;
        #20 reset = 0; enable = 1;
        #100;
        $finish;
    end
endmodule
