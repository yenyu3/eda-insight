module uart_tx #(
    parameter BAUD_DIV = 4
)(
    input clk,
    input rst_n,
    input start,
    input [7:0] data_in,
    output reg tx,
    output reg tx_busy
);
    localparam IDLE  = 2'd0;
    localparam START = 2'd1;
    localparam DATA  = 2'd2;
    localparam STOP  = 2'd3;

    reg [1:0] state, next_state;
    reg [15:0] baud_cnt, next_baud_cnt;
    reg [2:0] bit_cnt, next_bit_cnt;
    reg [7:0] shift_reg, next_shift_reg;
    reg tx_next, tx_busy_next;

    always @(*) begin
        next_state = state;
        next_baud_cnt = baud_cnt;
        next_bit_cnt = bit_cnt;
        next_shift_reg = shift_reg;
        tx_next = tx;
        tx_busy_next = tx_busy;

        case (state)
            IDLE: begin
                tx_next = 1'b1;
                tx_busy_next = 1'b0;
                if (start) begin
                    next_state = START;
                    next_baud_cnt = 16'd0;
                    next_shift_reg = data_in;
                    tx_busy_next = 1'b1;
                end
            end

            START: begin
                tx_next = 1'b0;
                tx_busy_next = 1'b1;
                if (baud_cnt >= BAUD_DIV - 1) begin
                    next_state = DATA;
                    next_baud_cnt = 16'd0;
                    next_bit_cnt = 3'd0;
                end else begin
                    next_baud_cnt = baud_cnt + 16'd1;
                end
            end

            DATA: begin
                tx_next = shift_reg[0];
                tx_busy_next = 1'b1;
                if (baud_cnt >= BAUD_DIV - 1) begin
                    next_baud_cnt = 16'd0;
                    next_shift_reg = {1'b0, shift_reg[7:1]};
                    if (bit_cnt >= 3'd7) begin
                        next_state = STOP;
                    end else begin
                        next_bit_cnt = bit_cnt + 3'd1;
                    end
                end else begin
                    next_baud_cnt = baud_cnt + 16'd1;
                end
            end

            STOP: begin
                tx_next = 1'b1;
                tx_busy_next = 1'b1;
                if (baud_cnt >= BAUD_DIV - 1) begin
                    next_state = IDLE;
                    next_baud_cnt = 16'd0;
                    tx_busy_next = 1'b0;
                end else begin
                    next_baud_cnt = baud_cnt + 16'd1;
                end
            end

            default: begin
                next_state = IDLE;
                tx_next = 1'b1;
                tx_busy_next = 1'b0;
                next_baud_cnt = 16'd0;
                next_bit_cnt = 3'd0;
                next_shift_reg = 8'd0;
            end
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            baud_cnt <= 16'd0;
            bit_cnt <= 3'd0;
            shift_reg <= 8'd0;
            tx <= 1'b1;
            tx_busy <= 1'b0;
        end else begin
            state <= next_state;
            baud_cnt <= next_baud_cnt;
            bit_cnt <= next_bit_cnt;
            shift_reg <= next_shift_reg;
            tx <= tx_next;
            tx_busy <= tx_busy_next;
        end
    end
endmodule
