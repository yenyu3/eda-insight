// Error demo sample: this module intentionally has a functional bug.
// The testbench expects addition, but bit 0 is implemented as XOR with carry dropped.
module broken_adder_8bit (
    input [7:0] a,
    input [7:0] b,
    output [7:0] sum,
    output carry
);

wire [8:0] partial;

assign partial = {1'b0, a[7:1], (a[0] ^ b[0])} + {1'b0, b[7:1], 1'b0};
assign sum = partial[7:0];
assign carry = partial[8];

endmodule
