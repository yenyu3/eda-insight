module broken_adder_8bit(
    input  [7:0] a,
    input  [7:0] b,
    output [7:0] sum
);
    // 故意做錯：少算 1
    assign sum = a + b - 8'd1;
endmodule
