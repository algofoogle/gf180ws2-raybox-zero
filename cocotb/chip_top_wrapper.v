`default_nettype none
`timescale 1ns / 1ps

module chip_top_wrapper #(
    // Power/ground pads for I/O
    parameter NUM_DVDD_PADS = `NUM_DVDD_PADS,
    parameter NUM_DVSS_PADS = `NUM_DVSS_PADS,

    // Power/ground pads for core
    parameter NUM_VDD_PADS = `NUM_VDD_PADS,
    parameter NUM_VSS_PADS = `NUM_VSS_PADS,

    // Signal pads
    parameter NUM_INPUT_PADS = `NUM_INPUT_PADS,
    parameter NUM_BIDIR_PADS = `NUM_BIDIR_PADS,
    parameter NUM_ANALOG_PADS = `NUM_ANALOG_PADS
)
(
    // Inputs coming from cocotb:
`ifdef USE_POWER_PINS
    inout VDD,
    inout VSS,
`endif

    input clk,
    input rst_n,
    input spi_sclk,
    input spi_mosi,
    input spi_csb,
    input debug,
    input inc_px,
    input inc_py,
    input registered_outputs,
    input tex_pmod_type,
    input gen_texb
);

    wire [NUM_INPUT_PADS-1:0] input_PAD;
    wire [NUM_BIDIR_PADS-1:0] bidir_PAD;
    wire [NUM_ANALOG_PADS-1:0] analog_PAD;


    assign bidir_PAD[0] = spi_sclk;
    assign bidir_PAD[1] = spi_mosi;
    assign bidir_PAD[2] = spi_csb;
    assign bidir_PAD[3] = debug;
    assign bidir_PAD[4] = inc_px;
    assign bidir_PAD[5] = inc_py;
    assign bidir_PAD[6] = registered_outputs;
    assign bidir_PAD[7] = tex_pmod_type;

    // Specific outputs for raybox-zero:
    // RrGgBb and H/Vsync pin ordering is influenced by Tiny VGA PMOD
    // (https://tinytapeout.com/specs/pinouts/#vga-output)
    wire [1:0] rr = {bidir_PAD[16], bidir_PAD[20]};
    wire [1:0] gg = {bidir_PAD[17], bidir_PAD[21]};
    wire [1:0] bb = {bidir_PAD[18], bidir_PAD[22]};
    wire [5:0] rgb = {rr,gg,bb}; // Just used by cocotb test bench for convenient checks.
    wire hsync_n    = bidir_PAD[23];
    wire vsync_n    = bidir_PAD[19];

    // wire tex_csb    = bidir_PAD[8+0];
    // wire tex_out0   = bidir_PAD[8+1];
    // wire tex_sclk   = bidir_PAD[8+3];

    // wire [2:0] tex_io;

    // // 8+0 is an output.
    // assign bidir_PAD[8+1] = tex_io[0]; //NOTE: Bidirectional function.
    // assign bidir_PAD[8+2] = tex_io[1];
    // 8+3 is an output
    assign bidir_PAD[8+4] = 1'b0; // SPARE input.
    assign bidir_PAD[8+5] = gen_texb;
    // assign bidir_PAD[8+6] = tex_io[2];
    assign bidir_PAD[8+7] = 1'b0; // UNUSED tex_io[3]


    chip_top chip_top(
    `ifdef USE_POWER_PINS
        .VDD            (VDD),
        .VSS            (VSS),
        // .DVDD           (DVDD),
        // .DVSS           (DVSS),
    `endif
        .clk_PAD        (clk),
        .rst_n_PAD      (rst_n),
        .input_PAD      (input_PAD),
        .bidir_PAD      (bidir_PAD),
        .analog_PAD     (analog_PAD)
    );

endmodule
