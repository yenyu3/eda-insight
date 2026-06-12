module broken_adder_8bit_tb;
    reg [7:0] a;
    reg [7:0] b;
    wire [7:0] sum;
    wire carry;

    broken_adder_8bit uut (
        .a(a),
        .b(b),
        .sum(sum),
        .carry(carry)
    );

    task check_add;
        input [7:0] lhs;
        input [7:0] rhs;
        reg [8:0] expected;
        begin
            a = lhs;
            b = rhs;
            expected = lhs + rhs;
            #1;
            if ({carry, sum} !== expected) begin
                $display("ERROR: %0d + %0d expected %0d, got %0d at time %0t",
                         lhs, rhs, expected, {carry, sum}, $time);
                $fatal(1);
            end
        end
    endtask

    initial begin
        $dumpfile("broken_adder_8bit.vcd");
        $dumpvars(0, broken_adder_8bit_tb);

        check_add(8'd2, 8'd4);
        check_add(8'd15, 8'd1);
        check_add(8'd255, 8'd1);

        $display("broken_adder_8bit_tb PASS - this line should not be reached");
        $finish;
    end
endmodule
