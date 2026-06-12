module pulse_stretcher_v2_tb;
    reg clk;
    reg reset;
    reg pulse_in;
    wire pulse_out;

    pulse_stretcher_v2 #(.WIDTH(4)) uut (
        .clk(clk),
        .reset(reset),
        .pulse_in(pulse_in),
        .pulse_out(pulse_out)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    task expect_output;
        input expected;
        begin
            @(negedge clk);
            if (pulse_out !== expected) begin
                $display("ERROR: expected pulse_out=%0d, got %0d at time %0t", expected, pulse_out, $time);
                $fatal(1);
            end
        end
    endtask

    initial begin
        $dumpfile("pulse_stretcher_v2.vcd");
        $dumpvars(0, pulse_stretcher_v2_tb);

        reset = 1'b1;
        pulse_in = 1'b0;
        repeat (2) @(negedge clk);
        reset = 1'b0;

        pulse_in = 1'b1;
        expect_output(1'b1);
        pulse_in = 1'b0;
        expect_output(1'b1);
        expect_output(1'b1);
        expect_output(1'b1);
        expect_output(1'b0);
        expect_output(1'b0);

        pulse_in = 1'b1;
        expect_output(1'b1);
        pulse_in = 1'b0;
        expect_output(1'b1);
        expect_output(1'b1);
        pulse_in = 1'b1;
        expect_output(1'b1);
        pulse_in = 1'b0;
        expect_output(1'b1);
        expect_output(1'b1);
        expect_output(1'b1);
        expect_output(1'b0);

        $display("pulse_stretcher_v2_tb PASS");
        $finish;
    end
endmodule
