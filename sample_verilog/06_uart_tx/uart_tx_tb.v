`timescale 1ns/1ps

module uart_tx_tb;
    reg clk;
    reg rst_n;
    reg start;
    reg [7:0] data_in;
    wire tx;
    wire tx_busy;

    uart_tx #(.BAUD_DIV(4)) dut(
        .clk(clk),
        .rst_n(rst_n),
        .start(start),
        .data_in(data_in),
        .tx(tx),
        .tx_busy(tx_busy)
    );

    always #5 clk = ~clk;

    task send_byte(input [7:0] d);
    begin
        @(posedge clk);
        data_in = d;
        start = 1'b1;
        @(posedge clk);
        start = 1'b0;
        wait(tx_busy == 1'b0);
        #20;
    end
    endtask

    initial begin
        $dumpfile("uart_tx.vcd");
        $dumpvars(0, uart_tx_tb);

        clk = 0;
        rst_n = 0;
        start = 0;
        data_in = 8'd0;

        #20 rst_n = 1;

        send_byte(8'h48); // 'H'
        send_byte(8'h69); // 'i'
        send_byte(8'h00);
        send_byte(8'hFF);

        #100 $finish;
    end
endmodule
