module sramLine
#(
    parameter WIDTH = 1920,                 //Width of sram line
    parameter CHAN = 3,
    parameter BITS = 16,                      //Data Width
    parameter PORTS = 2,                    //Number of ports
    parameter AW = $clog2(WIDTH)            //Address width
)
(
    input logic clk,
    input logic rstn,
    input bit [PORTS-1:0] ren,         //This an active high signal for read enable
    input bit [PORTS-1:0] wen,                        //this is active high for write enable
    input logic [PORTS-1:0][AW-1:0] addr,  //address bus
    input logic [47:0] d,                 //input to be written
    output logic [47:0] q [PORTS-1:0]      //output bus
);

(* ram_style = "block" *) logic [47:0] data [WIDTH-1:0];
//logic [CHAN-1:0][BITS-1:0] data [WIDTH-1:0];

integer i;

always_ff @(posedge clk) begin
    if(ren[0]) begin
        q[0] <= data[addr[0]];
    end
    else begin
        q[0] <= 0;
    end
    
    if(wen[0]) begin
        data[addr[0]] <= d;
    end
end

always_ff @(posedge clk) begin
    if(ren[1]) begin
        q[1] <= data[addr[1]];
    end
    else begin
        q[1] <= 0;
    end
    
    if(wen[1]) begin
        data[addr[1]] <= d;
    end
end

endmodule

