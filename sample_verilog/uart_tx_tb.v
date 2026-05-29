module uart_tx_tb;
    reg        clk, rst;
    reg  [7:0] tx_data;
    reg        tx_valid;
    wire       tx;
    wire       tx_busy;

    // Use BAUD_DIV=4 so each bit = 4 clock periods = 40 ns
    // Full frame (10 bits) = 40 clock periods = 400 ns
    uart_tx #(.BAUD_DIV(4)) uut (
        .clk(clk), .rst(rst),
        .tx_data(tx_data), .tx_valid(tx_valid),
        .tx(tx), .tx_busy(tx_busy)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    // Task: send one byte and wait for transmission to complete
    task send_byte;
        input [7:0] data;
        begin
            @(posedge clk);
            tx_data  = data;
            tx_valid = 1'b1;
            @(posedge clk);
            tx_valid = 1'b0;
            // Wait until not busy
            @(negedge tx_busy);
            #20;
        end
    endtask

    initial begin
        $dumpfile("uart_tx.vcd");
        $dumpvars(0, uart_tx_tb);

        rst = 1; tx_data = 8'd0; tx_valid = 1'b0;
        #30 rst = 0;
        #10;

        // Send 'H' = 0x48 = 0100_1000 -> LSB-first: 0,0,0,1,0,0,1,0
        send_byte(8'h48);
        // Send 'i' = 0x69 = 0110_1001 -> LSB-first: 1,0,0,1,0,1,1,0
        send_byte(8'h69);
        // Send 0x00 (check zero byte)
        send_byte(8'h00);
        // Send 0xFF (check all-ones)
        send_byte(8'hFF);

        #100 $finish;
    end
endmodule
