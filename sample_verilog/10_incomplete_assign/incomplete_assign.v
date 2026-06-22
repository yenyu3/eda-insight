module incomplete_assign(
    input  sel,
    input  a,
    input  b,
    output reg y
);
    always @(*) begin
        if (sel) begin
            y = a;
        end
        // 故意沒有 else，容易形成 latch 風險
    end
endmodule
