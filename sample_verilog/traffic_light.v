// Moore FSM traffic light controller
// States: RED -> GREEN -> YELLOW -> RED
module traffic_light (
    input        clk,
    input        rst,
    input  [3:0] phase_len,   // clock cycles per green/red phase
    output reg   red,
    output reg   yellow,
    output reg   green
);

localparam S_RED    = 2'd0;
localparam S_GREEN  = 2'd1;
localparam S_YELLOW = 2'd2;

localparam YELLOW_LEN = 4'd3;

reg [1:0] state;
reg [3:0] timer;

// State + timer register
always @(posedge clk) begin
    if (rst) begin
        state <= S_RED;
        timer <= 4'd0;
    end else begin
        case (state)
            S_RED: begin
                if (timer >= phase_len - 1) begin
                    state <= S_GREEN;
                    timer <= 4'd0;
                end else begin
                    timer <= timer + 1;
                end
            end
            S_GREEN: begin
                if (timer >= phase_len - 1) begin
                    state <= S_YELLOW;
                    timer <= 4'd0;
                end else begin
                    timer <= timer + 1;
                end
            end
            S_YELLOW: begin
                if (timer >= YELLOW_LEN - 1) begin
                    state <= S_RED;
                    timer <= 4'd0;
                end else begin
                    timer <= timer + 1;
                end
            end
            default: begin
                state <= S_RED;
                timer <= 4'd0;
            end
        endcase
    end
end

// Moore output logic
always @(*) begin
    red    = (state == S_RED);
    yellow = (state == S_YELLOW);
    green  = (state == S_GREEN);
end

endmodule
