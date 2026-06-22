module traffic_light(
    input clk,
    input rst_n,
    input [3:0] phase_len,
    output reg red,
    output reg yellow,
    output reg green
);
    localparam RED    = 2'd0;
    localparam GREEN  = 2'd1;
    localparam YELLOW = 2'd2;

    reg [1:0] state, next_state;
    reg [3:0] timer, next_timer;

    always @(*) begin
        next_state = state;
        next_timer = timer;

        case (state)
            RED: begin
                if (timer >= phase_len - 1) begin
                    next_state = GREEN;
                    next_timer = 4'd0;
                end else begin
                    next_timer = timer + 4'd1;
                end
            end

            GREEN: begin
                if (timer >= phase_len - 1) begin
                    next_state = YELLOW;
                    next_timer = 4'd0;
                end else begin
                    next_timer = timer + 4'd1;
                end
            end

            YELLOW: begin
                if (timer >= 4'd2) begin
                    next_state = RED;
                    next_timer = 4'd0;
                end else begin
                    next_timer = timer + 4'd1;
                end
            end

            default: begin
                next_state = RED;
                next_timer = 4'd0;
            end
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= RED;
            timer <= 4'd0;
        end else begin
            state <= next_state;
            timer <= next_timer;
        end
    end

    always @(*) begin
        red    = 1'b0;
        yellow = 1'b0;
        green  = 1'b0;

        case (state)
            RED:    red = 1'b1;
            GREEN:  green = 1'b1;
            YELLOW: yellow = 1'b1;
            default: red = 1'b1;
        endcase
    end
endmodule
