module sram
#(
	parameter PORTS = 2,
	parameter WIDTH = 1920,
	parameter BITS = 16,
	parameter CHAN = 3,
	parameter AW = $clog2(WIDTH),
	parameter CON = 1,
	parameter a = 1924,
	parameter SH_a = 3,
	parameter SW_a = 3,
	parameter LINES = 3
)
(
	input logic clk,
	input logic rstn,
	input logic [PORTS-1:0][AW-1:0] addr [LINES-1:0],
	input logic [PORTS-1:0] ren [LINES-1:0],
	input logic [PORTS-1:0] wen [LINES-1:0],
	input logic [CHAN-1:0][BITS-1:0] Idata,
	output logic [CHAN-1:0][BITS-1:0] Odata [LINES-1:0][PORTS-1:0]
);


genvar j;
generate
	for (j=0;j<LINES;j++) begin
		sramLine #(
			.CHAN (CHAN),
			.BITS (BITS),
			.AW (AW),
			.PORTS (PORTS),
			.WIDTH (WIDTH)
		) sram_line (
			.clk (clk),
			.rstn (rstn),
			.addr (addr[j]),
			.d (Idata),
			.q (Odata[j]),
			// .data (data[j]),
			.wen (wen[j]),
			.ren (ren[j])
		);
	end
endgenerate

endmodule

