// SPDX-FileCopyrightText: © 2026 Anton Maurovic
// SPDX-License-Identifier: Apache-2.0

`default_nettype none

// # The pinout of your project. Leave unused pins blank. DO NOT delete or add any pins.
// # This section is for the datasheet/website. Use descriptive names (e.g., RX, TX, MOSI, SCL, SEG_A, etc.).
// pinout:
//   # Inputs
//   ui[0]: spi_sck
//   ui[1]: spi_sdi  # aka MOSI
//   ui[2]: spi_csb  # aka ss_n
//   ui[3]: debug    # Show debug overlays on screen?
//   ui[4]: inc_px   # Increment px
//   ui[5]: inc_py   # Increment py
//   ui[6]: reg      # Present registered or unregistered outputs?
//   ui[7]: tex_pmod_type
//   #NOTE: For texture_pmod_type:
//   # 0=Moser's QSPI PMOD;
//   #   In this mode, it's assumed gen_texb is not used, i.e. we're always using
//   #   QSPI textures when tex_pmod_type==0. This eliminates the need for an external
//   #   pull-up resistor; if it weren't for this, then:
//   #     The PMOD should have a weak pull-up applied to uio[5] (its io3 pin).
//   #     This would ensure gen_texb is DISABLED during the times when it would otherwise float.
//   #     Besides that, the memory should be written with io3==1 in the whole ROM so that any
//   #     read doesn't override the weak pull-up and activate gen_texb mode.
//   #     NOTE: Looks like there are jumpers to enable/disable the chips (must cut traces first)...?
//   # 1=Digilent SPI PMOD;
//   #   Expect uio[5] (RSTb) is weakly pulled up, but can be pulled low for GEN_TEXb instead.

//   # Outputs: Tiny VGA PMOD (https://tinytapeout.com/specs/pinouts/#vga-output)
//   uo[0]: red[1]
//   uo[1]: green[1]
//   uo[2]: blue[1]
//   uo[3]: vsync_n
//   uo[4]: red[0]
//   uo[5]: green[0]
//   uo[6]: blue[0]
//   uo[7]: hsync_n

//   # Bidirectional pins
//   #NOTE: The following are compatible with https://digilent.com/reference/pmod/pmodsf3/start
//   # and https://github.com/mole99/qspi-pmod (depending on which is selected by tex_pmod_type).
//   ######## type=1                    type=0
//   uio[0]: 'Out: digilent_tex_csb   / Out: moser_tex_csb'
//   uio[1]: 'I/O: digilent_tex_io0   / I/O: moser_tex_io0'
//   uio[2]: 'In:  digilent_tex_io1   / In:  moser_tex_io1'
//   uio[3]: 'Out: digilent_tex_sclk  / Out: moser_tex_sclk'
//   uio[4]: 'In:  SPARE              / In:  moser_tex_io2'
//   uio[5]: 'In:  gen_texb           / In:  moser_tex_io3'     # aka GEN_TEXb, aka use_texture_spi (when high) -- ignored when tex_pmod_type==0.
//   uio[6]: 'In:  digilent_tex_io2   / N/A: moser_CS1'         # With type==0 it outputs 1 (to disable RAM A).
//   uio[7]: 'In:  digilent_tex_io3   / N/A: moser_CS2'         # With type==0 it outputs 1 (to disable RAM B). NOTE: Otherwise unused for type==1, or MAYBE SPARE


// Pin mapping:
// Reserved:
//      clk
//      rst_n
// bidir_in:
//  0   spi_clk
//  1   spi_sdi
//  2   spi_csb
//  3   debug
//  4   inc_px
//  5   inc_py
//  6   reg
//  7   tex_pmod_type:
/////// type=1 -------------------- type=0 ///////
//  8   OUT:    digilent_tex_csb    / Out: moser_tex_csb
//  9   I/O:    digilent_tex_io0    / I/O: moser_tex_io0
//  10  IN:     digilent_tex_io1    / moser_tex_io1
//  11  OUT:    digilent_tex_sclk  / Out: moser_tex_sclk
//  12  IN:     SPARE               / moser_tex_io2
//  13  IN:     gen_texb            / moser_tex_io3
//  14  IN:     digilent_tex_io2    / moser_CS1
//  15  IN:     digilent_tex_io3    / moser_CS2
// OUTPUTS:
//  16  red[1]
//  17  green[1]
//  18  blue[1]
//  19  vsync_n
//  20  red[0]
//  21  green[0]
//  22  blue[0]
//  23  hsync_n
// EXTRA OUTPUTS, for later:
//  24  hblank
//  25  vblank
//  26  hmax
//  27  vmax
//  37:28  vpos




module chip_core #(
    parameter NUM_INPUT_PADS,
    parameter NUM_BIDIR_PADS,
    parameter NUM_ANALOG_PADS
    )(
`ifdef USE_POWER_PINS
    inout  wire VDD,
    inout  wire VSS,
`endif
    
    input  wire clk,       // clock
    input  wire rst_n,     // reset (active low)
    
    input  wire [NUM_INPUT_PADS-1:0] input_in,   // Input value
    output wire [NUM_INPUT_PADS-1:0] input_pu,   // Pull-up
    output wire [NUM_INPUT_PADS-1:0] input_pd,   // Pull-down

    input  wire [NUM_BIDIR_PADS-1:0] bidir_in,   // Input value
    output wire [NUM_BIDIR_PADS-1:0] bidir_out,  // Output value
    output wire [NUM_BIDIR_PADS-1:0] bidir_oe,   // Output enable
    output wire [NUM_BIDIR_PADS-1:0] bidir_cs,   // Input type (0=CMOS Buffer, 1=Schmitt Trigger)
    output wire [NUM_BIDIR_PADS-1:0] bidir_sl,   // Slew rate (0=fast, 1=slow)
    output wire [NUM_BIDIR_PADS-1:0] bidir_ie,   // Input enable
    output wire [NUM_BIDIR_PADS-1:0] bidir_pu,   // Pull-up
    output wire [NUM_BIDIR_PADS-1:0] bidir_pd,   // Pull-down

    inout  wire [NUM_ANALOG_PADS-1:0] analog  // Analog
);

    // See here for usage: https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/digital.html
    
    wire [9:0] hpos, vpos;

    assign bidir_oe[7:0] = '0; // [7:0] are inputs.

    wire spi_sclk       = bidir_in[0];
    wire spi_mosi       = bidir_in[1];
    wire spi_csb        = bidir_in[2];
    wire debug          = bidir_in[3];
    wire inc_px         = bidir_in[4];
    wire inc_py         = bidir_in[5];
    wire i_reg          = bidir_in[6];
`ifndef NO_EXTERNAL_TEXTURES
    wire tex_pmod_type  = bidir_in[7];
    //NOTE: For tex_pmod_type:
    //   0=Moser's QSPI PMOD; can have a weak pull-up on uio[5] (io3), and ensure io3 bits are 1 in ROM to avoid GEN_TEXb. NOTE: Looks like there are jumpers to enable/disable the chips...?
    //   1=Digilent SPI PMOD; hence expect uio[5] (RSTb) is weakly pulled up anyway, but can be pulled low for GEN_TEXb instead.
    wire tex_csb;
    wire tex_out0;
    wire tex_oeb0;
    wire tex_sclk;
    //SMELL: Change these to always_comb blocks?
    wire [3:0] tex_in = 
        tex_pmod_type ?
        {
            // tex_pmod_type==1: Digilent SPI PMOD
            bidir_in[8+7],  // (io3 unused)
            bidir_in[8+6],
            bidir_in[8+2],
            bidir_in[8+1]
        } : {
            // tex_pmod_type==0: Moser's QSPI PMOD
            bidir_in[8+5],  // (io3 unused)
            bidir_in[8+4],
            bidir_in[8+2],
            bidir_in[8+1]
        };
    wire gen_tex = tex_pmod_type ?
        ~bidir_in[8+5] :  // gen_tex (actually gen_texb) can be used in 'Digilent SPI PMOD'-mode.
        1'b0;         // Disable gen_tex when using Moser's QSPI PMOD.
`endif // NO_EXTERNAL_TEXTURES

    ///////////////// REGISTERED VGA OUTPUTS: /////////////////
    wire  [5:0] rgb;
    wire        vsync_n, hsync_n;
    reg   [7:0] registered_vga_output; // Registered VGA outputs.
    wire  [7:0] unregistered_vga_output = {
        // Original `rgb` order is {BbGgRr}. Map this order, plus H/Vsync, per Tiny VGA PMOD
        // (https://tinytapeout.com/specs/pinouts/#vga-output):
        hsync_n, rgb[4], rgb[2], rgb[0], // [7:4] = {hbgr}
        vsync_n, rgb[5], rgb[3], rgb[1]  // [3:0] = {vBGR}
    };
    wire hblank, hmax;
    wire vblank, vmax;

    always @(posedge clk) registered_vga_output <= unregistered_vga_output;

    assign bidir_out[23:16] = i_reg ? registered_vga_output : unregistered_vga_output;

    // bidir_out[16] = red[1]
    // bidir_out[17] = green[1]
    // bidir_out[18] = blue[1]
    // bidir_out[19] = vsync_n
    // bidir_out[20] = red[0]
    // bidir_out[21] = green[0]
    // bidir_out[22] = blue[0]
    // bidir_out[23] = hsync_n

    assign bidir_oe[23:16] = '1; // All 1 (outputs).
    ////////////////////////////////////////////////////////////////////

    assign bidir_out[37:28] = vpos;
    assign bidir_oe[37:28] = '1;


    logic _unused;
`ifdef NO_EXTERNAL_TEXTURES
    assign _unused = &{input_in, bidir_in[NUM_BIDIR_PADS-1:8], 1'b0};
`else // !NO_EXTERNAL_TEXTURES
    assign _unused = &{input_in, bidir_in[NUM_BIDIR_PADS-1:16], bidir_in[8+3], bidir_in[8+0], 1'b0};
`endif // NO_EXTERNAL_TEXTURES


    rbzero rbzero(
        .clk        (clk),
        .reset      (~rst_n),

        // SPI peripheral for POV and REG access:
        //SMELL: Fix alternate support for NOT USE_POV_VIA_SPI_REGS:
        .i_reg_sclk (spi_sclk),
        .i_reg_mosi (spi_mosi),
        .i_reg_ss_n (spi_csb),

`ifndef NO_EXTERNAL_TEXTURES
        // SPI controller interface for reading SPI flash memory (i.e. textures):
        .o_tex_csb  (tex_csb),
        .o_tex_sclk (tex_sclk),
        .o_tex_out0 (tex_out0),
        .o_tex_oeb0 (tex_oeb0), // Direction control for io[0] (WARNING: OEb, not OE).
        .i_tex_in   (tex_in), //NOTE: io[3] is unused, currently.
`endif // NO_EXTERNAL_TEXTURES

`ifdef USE_MAP_OVERLAY
        // Debug/demo signals:
        .i_debug_m  (debug), // Map debug overlay
`endif // USE_MAP_OVERLAY
`ifdef TRACE_STATE_DEBUG
        .i_debug_t  (debug), // Trace debug overlay
`endif // TRACE_STATE_DEBUG
`ifdef USE_DEBUG_OVERLAY
        .i_debug_v  (debug), // Vectors debug overlay
`endif // USE_DEBUG_OVERLAY
        .i_inc_px   (inc_px),
        .i_inc_py   (inc_py),
`ifndef NO_EXTERNAL_TEXTURES
        .i_gen_tex  (gen_tex), // 1=Use bitwise-generated textures instead of SPI texture memory.
`endif // NO_EXTERNAL_TEXTURES
        // .o_vinf     (vinf),
        .o_hmax     (hmax),
        .o_vmax     (vmax),
        // VGA outputs:
        .o_hblank   (hblank),
        .o_vblank   (vblank),
        .hpos       (hpos),
        .vpos       (vpos),
        .hsync_n    (hsync_n), // Unregistered.
        .vsync_n    (vsync_n), // Unregistered.
        .rgb        (rgb)
    );

  // 1 = output, 0 = input:
`ifdef NO_EXTERNAL_TEXTURES
    assign bidir_oe[15:8] = '0;
    assign bidir_out[15:8] = '0;
`else // !NO_EXTERNAL_TEXTURES
  //NOTE: Only bidir_oe[15:14] directions are different between these two sets,
  // but both are included in full to help highlight their pin differences.
  assign bidir_oe[15:8] = 
    tex_pmod_type ?
    {
      // tex_pmod_type==1: Digilent SPI PMOD
      1'b0,       // uio[7]: tex_io3        input (UNUSED).
      1'b0,       // uio[6]: tex_io2        input.
      1'b0,       // uio[5]: gen_texb       input.
      1'b0,       // uio[4]: SPARE          input.
      1'b1,       // uio[3]: tex_sclk       OUTPUT.
      1'b0,       // uio[2]: tex_io1        input.
      ~tex_oeb0,  // uio[1]: tex_io0        BIDIRECTIONAL. Inverted; rbzero gives OEb, need OE.
      1'b1        // uio[0]: tex_csb        OUTPUT.
    } : {
      // tex_pmod_type==0: Moser's QSPI PMOD
      1'b1,       // uio[7]: CS2            OUTPUT.
      1'b1,       // uio[6]: CS1            OUTPUT.
      1'b0,       // uio[5]: tex_io3        input (UNUSED).
      1'b0,       // uio[4]: tex_io2        input.
      1'b1,       // uio[3]: tex_sclk       OUTPUT.
      1'b0,       // uio[2]: tex_io1        input.
      ~tex_oeb0,  // uio[1]: tex_io0        BIDIRECTIONAL. Inverted; rbzero gives OEb, need OE.
      1'b1        // uio[0]: tex_csb        OUTPUT.
    };
  assign bidir_out[15:8] =
    tex_pmod_type ?
    {
      // tex_pmod_type==1: Digilent SPI PMOD
      1'b0,       // uio[7]: 
      1'b0,       // uio[6]: 
      1'b0,       // uio[5]: 
      1'b0,       // uio[4]: 
      tex_sclk,   // uio[3]: tex_sclk
      1'b0,       // uio[2]: 
      tex_out0,   // uio[1]: tex_io0 (BIDIR)
      tex_csb     // uio[0]: tex_csb
    } : {
      // tex_pmod_type==0: Moser's QSPI PMOD
      1'b1,       // uio[7]: CS2 (permanently high, i.e. disabled)
      1'b1,       // uio[6]: CS1 (permanently high, i.e. disabled)
      1'b0,       // uio[5]: 
      1'b0,       // uio[4]: 
      tex_sclk,   // uio[3]: tex_sclk
      1'b0,       // uio[2]: 
      tex_out0,   // uio[1]: tex_io0 (BIDIR)
      tex_csb     // uio[0]: tex_csb
    };
`endif // NO_EXTERNAL_TEXTURES

    assign bidir_oe[27:24] = '1; // All 1: Outputs.
    assign bidir_out[24] = hblank;
    assign bidir_out[25] = vblank;
    assign bidir_out[26] = hmax;
    assign bidir_out[27] = vmax;

    // Disable pull-up and pull-down for input
    assign input_pu = '0;
    assign input_pd = '0;

    // Set the bidir as output
    // assign bidir_oe = '1; // 1=Output (for all). This syntax is equivalent to: assign bidir_oe={NUM_BIDIR_PADS{1'b1}};
    assign bidir_oe[NUM_BIDIR_PADS-1:38] = '0; // Higher pads are unused inputs.
    assign bidir_out[NUM_BIDIR_PADS-1:38] = '0;
    assign bidir_out[7:0] = '0;
    assign bidir_ie = ~bidir_oe; // Enable input buffers only on pads that are inputs.
    assign bidir_cs = '0; // 0=CMOS buffer.
    assign bidir_sl = '0; // 0=Fast slew.
    assign bidir_pu = '0; // Disable pull-up.
    assign bidir_pd = '0; // Disable pull-down.
    

endmodule

`default_nettype wire
