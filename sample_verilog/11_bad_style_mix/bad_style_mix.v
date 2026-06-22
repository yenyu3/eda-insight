module bad_style_mix(
    input clk,
    input rst_n,
    input en,
    input [3:0] data_in,
    output reg [3:0] data_out
);
    reg [3:0] temp;
    wire unused_wire;

    assign unused_wire = 1'b0;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_out <= 4'd0;
        end else if (en) begin
            data_out <= temp;
        end
    end

    always @(*) begin
        if (en) begin
            temp = data_in;
        end
    end
endmodule
