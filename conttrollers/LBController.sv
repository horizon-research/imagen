/* 
    * Linebuffer controller: All it does is tells which line to read from.
    * this will be invoked for every accesser, atleast that is the plan right now.
    * @param LINE_BITS number of bits to address the number of lines.
    * @param 
 */
module LBController
#(
    parameter LINES = 4,
    parameter LINE_BITS = $clog2(LINES),
    parameter WIDTH = 1920,
    parameter OFFSET = 0,
    parameter AW = $clog2(WIDTH),
    parameter SW = 1,
    parameter SH = 1,
    parameter PAD_TOP = 1,
    parameter PAD_RIGHT = 1,
    parameter PAD_LEFT = 1,
    parameter PORTS = 2
)
(
    input logic clk,
    input logic valid,
    input logic start,
    output logic [LINE_BITS-1:0] addrX [SH-1:0],         //The first line that stencil accesses
    output logic [AW-1:0] addrY,        //The column of pixels that is being shifted to the shift register array  
    output logic rowComplete,                    //tell if the row is complete.
    output logic [PAD_TOP:0] topPadMask,
    output logic [PAD_LEFT:0] leftPadMask,
    output logic [PAD_RIGHT:0] rightPadMask
);

logic [AW-1:0] colNum;
logic [LINE_BITS-1:0] lineNum;
logic [AW-1:0] colNumNext;              //Next column to shift
logic [LINE_BITS-1:0] lineNumNext;              //Next line
logic colDone;
logic linesDone;
logic padRowDone;
logic [PAD_TOP:0] topPadMaskNext;
logic [PAD_LEFT:0] leftPadMaskNext;
logic [PAD_RIGHT:0] rightPadMaskNext;


always_ff @(posedge clk or negedge start) begin
    if(!start) begin
        colNum <= OFFSET;
    end
    else if(rowComplete) begin
        colNum <= '0;
    end
    else begin
        colNum <= colNumNext;
    end
end

//assign colNumNext = valid? (colDone? 'd0 : colNum+1'd1) : colNum;
assign colNumNext = valid? colNum+1'd1 : colNum;

always_ff @(posedge clk or negedge start) begin
    if (!start) begin
        rowComplete <= '0;
    end
    else if(colDone) begin
        rowComplete <= '1;
    end
    else begin
        rowComplete <= '0;
    end
end

assign colDone = colNumNext == WIDTH-1?1'b1:1'b0;


assign linesDone = ((lineNum == LINES-1) && rowComplete)? 'd1 : 0;

always_ff @(posedge clk or negedge start) begin
    if(!start) begin
        topPadMask<=PAD_TOP;
    end
    else if (rowComplete) begin
        topPadMask<=topPadMaskNext;
    end
end

assign topPadMaskNext = valid?(topPadMask==0? 'd0 : topPadMask - 1'd1) : topPadMask;

always_ff @(posedge clk or negedge start) begin
    if(!start) begin
        leftPadMask <= PAD_LEFT;
    end
    else if (rowComplete) begin
        leftPadMask<=PAD_LEFT;
    end
    else begin 
        leftPadMask <= leftPadMaskNext;
    end
end

assign leftPadMaskNext = valid?(leftPadMask==0? 'd0 : (rightPadMask==0? leftPadMask - 1'd1: leftPadMask)) : leftPadMask;

always_ff @(posedge clk or negedge start) begin
    if(!start) begin
        rightPadMask <= 0;
    end
    else if (rowComplete) begin
        rightPadMask<=PAD_RIGHT;
    end
    else begin 
        rightPadMask <= rightPadMaskNext;
    end
end

assign rightPadMaskNext = valid?(rightPadMask==0? 'd0 : rightPadMask - 1'd1) : rightPadMask;

always_ff @(posedge clk or negedge start) begin
    if (!start) begin
        lineNum <= '0;
    end
    else if (linesDone && rowComplete) begin
        lineNum <= '0;
    end
    else if (rowComplete) begin
        lineNum <= lineNumNext;
    end
    else begin
        //Do nothing
    end
end


assign lineNumNext = (valid)?(linesDone? 'd0 : (topPadMask>0)? 'd0 : lineNum+1) : lineNum;
assign addrY = colNum;
assign addrX[0] = lineNum-topPadMask;

genvar i;
generate
    for (i=1;i<SH;i++) begin
        assign addrX[i] = (addrX[i-1]==LINES-1)? 'd0 : addrX[i-1]+'d1;
    end
endgenerate

endmodule