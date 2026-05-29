module alu_8bit_tb;
    reg        clk, rst;
    reg  [7:0] a, b;
    reg  [2:0] op;
    wire [7:0] result;
    wire       zero, carry_out;

    alu_8bit uut (
        .clk(clk), .rst(rst),
        .a(a), .b(b), .op(op),
        .result(result), .zero(zero), .carry_out(carry_out)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    initial begin
        $dumpfile("alu_8bit.vcd");
        $dumpvars(0, alu_8bit_tb);

        rst = 1; a = 8'd0; b = 8'd0; op = 3'd0;
        #20 rst = 0;

        // ADD: 10 + 20 = 30
        a = 8'd10;  b = 8'd20;  op = 3'd0; #10;
        // ADD with carry: 200 + 100 = 300 -> result=44, carry=1
        a = 8'd200; b = 8'd100; op = 3'd0; #10;
        // SUB: 50 - 20 = 30
        a = 8'd50;  b = 8'd20;  op = 3'd1; #10;
        // AND: 0xFF & 0x0F = 0x0F
        a = 8'hFF;  b = 8'h0F;  op = 3'd2; #10;
        // OR: 0xF0 | 0x0F = 0xFF
        a = 8'hF0;  b = 8'h0F;  op = 3'd3; #10;
        // XOR: 0xAA ^ 0x55 = 0xFF
        a = 8'hAA;  b = 8'h55;  op = 3'd4; #10;
        // NOT: ~0xAA = 0x55
        a = 8'hAA;  op = 3'd5;  #10;
        // SHL: 0x01 << 1 = 0x02
        a = 8'h01;  op = 3'd6;  #10;
        // SHR: 0x80 >> 1 = 0x40
        a = 8'h80;  op = 3'd7;  #10;
        // ADD zero flag: 0 + 0 = 0
        a = 8'd0;   b = 8'd0;   op = 3'd0; #10;

        #20 $finish;
    end
endmodule
