`timescale 1ns/1ps

module broken_adder_8bit_tb;
    reg [7:0] a;
    reg [7:0] b;
    wire [7:0] sum;

    broken_adder_8bit dut(
        .a(a),
        .b(b),
        .sum(sum)
    );

    initial begin
        $dumpfile("broken_adder_8bit.vcd");
        $dumpvars(0, broken_adder_8bit_tb);

        a = 8'd15; b = 8'd1;
        #10;

        if (sum !== 8'd16) begin
            $display("ERROR: expected 16, got %0d", sum);
            $fatal;
        end

        #10 $finish;
    end
endmodule
