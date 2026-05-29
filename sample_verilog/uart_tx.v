// 8N1 UART Transmitter
// Frame format: 1 start bit (0), 8 data bits LSB-first, 1 stop bit (1)
module uart_tx #(
    parameter BAUD_DIV = 4  // Clock cycles per baud period (use small value for simulation)
) (
    input        clk,
    input        rst,
    input  [7:0] tx_data,
    input        tx_valid,
    output reg   tx,
    output reg   tx_busy
);

localparam IDLE  = 2'd0;
localparam START = 2'd1;
localparam DATA  = 2'd2;
localparam STOP  = 2'd3;

reg [1:0]  state;
reg [15:0] baud_cnt;
reg [7:0]  shift_reg;
reg [2:0]  bit_cnt;

wire baud_tick = (baud_cnt == BAUD_DIV - 1);

always @(posedge clk) begin
    if (rst) begin
        state     <= IDLE;
        tx        <= 1'b1;
        tx_busy   <= 1'b0;
        baud_cnt  <= 16'd0;
        shift_reg <= 8'd0;
        bit_cnt   <= 3'd0;
    end else begin
        baud_cnt <= baud_tick ? 16'd0 : baud_cnt + 1;

        case (state)
            IDLE: begin
                tx      <= 1'b1;
                tx_busy <= 1'b0;
                if (tx_valid) begin
                    shift_reg <= tx_data;
                    baud_cnt  <= 16'd0;
                    bit_cnt   <= 3'd0;
                    tx_busy   <= 1'b1;
                    state     <= START;
                end
            end

            START: begin
                tx <= 1'b0;                      // Start bit
                if (baud_tick)
                    state <= DATA;
            end

            DATA: begin
                tx <= shift_reg[0];              // LSB first
                if (baud_tick) begin
                    shift_reg <= {1'b0, shift_reg[7:1]};
                    if (bit_cnt == 3'd7)
                        state <= STOP;
                    else
                        bit_cnt <= bit_cnt + 1;
                end
            end

            STOP: begin
                tx <= 1'b1;                      // Stop bit
                if (baud_tick)
                    state <= IDLE;
            end
        endcase
    end
end

endmodule
