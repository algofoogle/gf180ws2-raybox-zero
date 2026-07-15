# SPDX-FileCopyrightText: © 2025 Project Template Contributors
# SPDX-License-Identifier: Apache-2.0

import os
import random
import logging
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer, Edge, RisingEdge, FallingEdge, ClockCycles
from cocotb_tools.runner import get_runner
import time
from os import environ as env
import re

HIGH_RES        = float(env.get('HIGH_RES')) if 'HIGH_RES' in env else None # If not None, scale H res by this, and step by CLOCK_PERIOD/HIGH_RES instead of unit clock cycles.
CLOCK_PERIOD    = float(env.get('CLOCK_PERIOD') or 40.0) # Default 40.0 (period of clk oscillator input, in nanoseconds)
FRAMES          =   int(env.get('FRAMES')       or   18) # Default 18 (total frames to render)
INC_PX          =   int(env.get('INC_PX')       or    1) # Default 1 (inc_px on)
INC_PY          =   int(env.get('INC_PY')       or    1) # Default 1 (inc_py on)
GEN_TEX         =   int(env.get('GEN_TEX')      or    0) # Default 0 (use tex ROM; no generated textures)
DEBUG_POV       =   int(env.get('DEBUG_POV')    or    1) # Default 1 (show POV vectors debug)
REG             =   int(env.get('REG')          or    0) # Default 0 (UNregistered outputs)
DEMO_MODE       =   int(env.get('DEMO_MODE')    or    0) # Default 0; If 1, disable all the other tests and just run the demo mode

print(f"""
Test parameters (can be overridden using ENV vars):
---     HIGH_RES: {HIGH_RES}
--- CLOCK_PERIOD: {CLOCK_PERIOD}
---       FRAMES: {FRAMES}
---       INC_PX: {INC_PX}
---       INC_PY: {INC_PY}
---      GEN_TEX: {GEN_TEX}
---    DEBUG_POV: {DEBUG_POV}
---          REG: {REG}
---    DEMO_MODE: {DEMO_MODE}
""")


sim = os.getenv("SIM", "icarus")
gl = os.getenv("GL", False)
pdk_root = os.getenv("PDK_ROOT", Path(__file__).resolve().parent / "../gf180mcu")
pdk = os.getenv("PDK", "gf180mcuD")
scl = os.getenv("SCL", "gf180mcu_fd_sc_mcu7t5v0")
pad = os.getenv("PAD", "gf180mcu_fd_io")
sram = os.getenv("SRAM", "gf180mcu_fd_ip_sram")
slot = os.getenv("SLOT", "1x1")

hdl_toplevel = "chip_top_wrapper"

def set_default_start_state(dut):
    # REG SPI interface inactive:
    dut.spi_sclk.value              = 0
    dut.spi_mosi.value              = 0
    dut.spi_csb.value               = 1
    # Enable debug display on-screen?
    dut.debug.value                 = DEBUG_POV
    # Enable demo mode(s) (player position auto-increment)?
    dut.inc_px.value                = INC_PX
    dut.inc_py.value                = INC_PY
    # Use generated textures instead of external texture SPI memory?
    dut.tex_pmod_type.value         = 1 # Digilent SPI PMOD.
    dut.gen_texb.value              = not GEN_TEX
    # Present registered outputs?
    dut.registered_outputs.value    = REG
    

class SPI:
    def __init__(self, dut, interface):
        self.dut = dut
        self.interface = interface
        if interface == 'reg':
            self.csb  = dut.spi_csb
            self.sclk = dut.spi_sclk
            self.mosi = dut.spi_mosi
        # elif interface == 'pov':
        #     self.csb = dut.pov_ss_n
        #     self.sclk = dut.pov_sclk
        #     self.mosi = dut.pov_mosi
        else:
            raise ValueError(f"Invalid interface {repr(interface)}; must be 'reg'")

    def __repr__(self):
        return f'SPI({self.interface})'

    async def spi_tick(self):
        # SPI interface expected to be stable at up to 20% of clock speed:
        #@@@SMELL: Need some jitter:
        await Timer(CLOCK_PERIOD*5.0, unit='ns')

    async def txn_start(self):
        self.csb.value = 1
        self.sclk.value = 0
        await self.spi_tick()
        self.csb.value = 0 # Active low.
    
    async def txn_send(self, data, count=None):
        if type(data) is int:
            data = bin(data)
            data = data[2:]
            if count is None:
                self.dut._log(f"WARNING: SPI.send_bits() called with int data {data} but no count")
        
        if count is not None:
            data = data.zfill(count)

        while len(data) > 0:
            self.mosi.value = int(data[0])
            data = data[1:]
            await self.spi_tick()
            self.sclk.value = 1 # Rising edge; clock in the bit.
            await self.spi_tick()
            self.sclk.value = 0 # Falling edge.

    async def txn_stop(self):
        await self.spi_tick()
        # Disable CSb; we're done:
        self.csb.value = 1
        self.sclk.value = 0
        await self.spi_tick()
    

async def spi_send_reg(dut, cmd, data, count=None, what=''):
    dut._log.info(f"spi_send_reg({repr(cmd)}, {repr(data)}) started [{what}]...")
    spi = SPI(dut, 'reg')
    await spi.txn_start()
    await spi.txn_send(cmd, 8)
    await spi.txn_send(data, count)
    await spi.txn_stop()
    dut._log.info(f"spi_send_reg() [{what}] DONE")


async def spi_send_pov(dut, data, what=''):
    dut._log.info(f"spi_send_pov({repr(data)}) started [{what}]...")
    spi = SPI(dut, 'reg')
    await spi.txn_start()
    await spi.txn_send(127, 8) # 127==CMD_POV
    await spi.txn_send(data, 74)
    await spi.txn_stop()
    dut._log.info(f"spi_send_pov() [{what}] DONE")


# async def spi_send_pov(dut, data, what=''):
#     dut._log.info(f"spi_send_pov({repr(data)}) started [{what}]...")
#     spi = SPI(dut, 'pov')
#     await spi.txn_start()
#     await spi.txn_send(data, 74)
#     await spi.txn_stop()
#     dut._log.info(f"spi_send_pov() [{what}] DONE")

async def async_run_all(steps):
    for step in steps:
        await step

def door_reg_string(x:int, y:int, wall:int, pos:int, frame:bool=True):
    return f"{x&0b111111:06b}{y&0b111111:06b}{wall&0b111:03b}{frame:01b}{pos&0b11111111:08b}"

CMD_SKY         = 0b0000_0000
CMD_FLOOR       = 0b0000_0001
CMD_LEAK        = 0b0000_0010
CMD_OTHER       = 0b0000_0011
CMD_VSHIFT      = 0b0000_0100

CMD_VOPTS       = 0b0000_0101
CMD_MAPD        = 0b0000_0110
CMD_MAPR        = 0b0000_0111

CMD_DOOR0       = 0b0000_1000
CMD_DOOR1       = 0b0000_1001
CMD_DOOR2       = 0b0000_1010
CMD_DOOR3       = 0b0000_1011

CMD_TEXADD0     = 0b0010_0000
CMD_TEXADD1     = 0b0010_0001
CMD_TEXADD2     = 0b0010_0010
CMD_TEXADD3     = 0b0010_0011
CMD_TEXADD4     = 0b0010_0100
CMD_TEXADD5     = 0b0010_0101
CMD_TEXADD6     = 0b0010_0110
CMD_TEXADD7     = 0b0010_0111

CMD_TEXADDENA   = 0b0100_0000
CMD_TRCTRL      = 0b0100_0001
CMD_POV         = 0b0111_1111






async def enable_power(dut):
    dut.VDD.value = 1
    dut.VSS.value = 0

async def start_clock(clock, freq=40):
    """Start the clock @ freq MHz"""
    c = Clock(clock, 1 / freq * 1000, "ns")
    cocotb.start_soon(c.start())


async def reset(reset, active_low=True, time_ns=1000):
    """Reset dut"""
    cocotb.log.info("Reset asserted...")

    reset.value = not active_low
    await Timer(time_ns, "ns")
    reset.value = active_low

    cocotb.log.info("Reset deasserted.")


# async def start_up(dut):
#     """Startup sequence"""
#     await set_defaults(dut)
#     if gl:
#         await enable_power(dut)
#     await start_clock(dut.clk)
#     await reset(dut.rst_n)

def set_gen_texb(dut, state):
    dut.gen_texb.value = state
    # dut.gen_texb.value = 0 # FORCED ON FOR NOW.


@cocotb.test()
async def test_frames(dut):
    """
    Generate a number of full video frames and write to rbz_basic_frame-###.ppm
    """

    # Create a logger for this testbench
    logger = logging.getLogger("my_testbench")

    # logger.info("Startup sequence...")

    dut._log.info("Starting test_frames...")

    frame_count = FRAMES # No. of frames to render.
    hrange = 800
    frame_height = 525
    vrange = frame_height
    hres = HIGH_RES or 1

    door_x, door_y = 13, 4
    door_wall = 1
    door_pos = 0

    print(f"Rendering {frame_count} full frame(s)...")

    set_default_start_state(dut)
    # Start with reset released:
    dut.rst_n.value = 1

    if gl:
        await enable_power(dut)

    clk = Clock(dut.clk, CLOCK_PERIOD, unit="ns")
    cocotb.start_soon(clk.start())

    # Wait 3 clocks...
    await ClockCycles(dut.clk, 3)
    # check_uio_out(dut)
    dut._log.info("Assert reset...")
    # ...then assert reset:
    dut.rst_n.value = 0
    # ...and wait another 10 clocks...
    await ClockCycles(dut.clk, 10)
    # check_uio_out(dut)
    dut._log.info("Release reset...")
    # ...then release reset:
    dut.rst_n.value = 1
    x_count = 0 # Counts unknown signal values.
    z_count = 0
    sample_count = 0 # Total count of pixels or samples.

    os.makedirs('frames_out', exist_ok=True)

    for frame in range(frame_count):
        render_start_time = time.time()

        nframe = frame + 1

        # --- Tests we do for each frame ---
        # (NOTE: New states pushed in one frame render in the next,
        # and this has been accounted for in the design below, hence `nframe`):
        # Frame index:
        # 000. Reset frame to initial view (slightly wonky; rayAddend in reset instead of prior vsync)
        # 001. Default behaviour (typically inc_px/py asserted from initial view)
        # 002. Default behaviour again
        # 003. inc_px/py disabled; frame should appear same as #2
        # 004. New POV loaded
        # 005. Should be same as #4
        # 006. inc_px/py reasserted; typically, existing POV should move slightly
        # 007. LEAK enabled
        # 008. VINF enabled
        # 009. LEAK disabled

        # NOTE: Each of these states are asserted at the start of the PRIOR
        # frame since they take effect on the NEXT frame, but the exceptions are
        # those which have an immediate combinatorial effect:
        # - gen_tex
        # - debug
        # - registered_outputs

        # If we just want DEMO_MODE, we disable all other updates.
        if DEMO_MODE:
            pass

        # Frame 0 will render as per normal (not really controllable).
        elif nframe in [1,2]:
            # Frames 1 & 2 will render per typical design behaviour.
            pass

        elif nframe == 3:
            # Frame 3 will turn off inc_px/py:
            dut.inc_px.value = 0
            dut.inc_py.value = 0
            # ALSO, use the map rectangle register:
            cocotb.start_soon(spi_send_reg(dut, CMD_MAPR,
                '000110' + '001000' +   # mapr_ax/y
                '001100' + '010010' +   # mapr_bx/y
                '1' +                   # mapr_erase
                '110',                  # mapr_wall
                what='Map rectangle'
            ))

        elif nframe == 4:
            # Set up a nice view for this frame.
            cocotb.start_soon(spi_send_pov(dut, '00110100011011100011111011011000000111101110000001000001111111000000011110', what='a nice POV'))

        elif nframe == 5:
            cocotb.start_soon(async_run_all([
                # Keep the same view as last time, but put in a door...
                spi_send_reg(dut, CMD_DOOR0, door_reg_string(door_x, door_y, door_wall, door_pos), what='Door'),
                # ...and set tracer wait states to 0:
                spi_send_reg(dut, CMD_TRCTRL, 0b00000_000, count=8, what='WAITS <= 0'),
            ]))

        elif nframe == 6:
            # Reassert inc_px/py inputs to see if the view moves...
            dut.inc_px.value = INC_PX
            dut.inc_py.value = INC_PY
            # ...AND do some async SPI stuff...
            door_pos = 8<<2
            cocotb.start_soon(async_run_all([
                # Change ceiling colour:
                spi_send_reg(dut, CMD_SKY, 0b01_00_01, count=6, what='SKY = dark purple'),
                # Update the door's sliding position:
                spi_send_reg(dut, CMD_DOOR0, door_reg_string(door_x, door_y, door_wall, door_pos), what='Door'),
            ]))

        elif nframe == 7:
            door_pos = 16<<2
            cocotb.start_soon(async_run_all([
                # Set a floor leak: Send SPI2 ('reg') command 2 (LEAK) and a corresponding value of 13:
                spi_send_reg(dut, CMD_LEAK, 13, count=6, what='set a LEAK'),
                # Update the door's sliding position:
                spi_send_reg(dut, CMD_DOOR0, door_reg_string(door_x, door_y, door_wall, door_pos), what='Door'),
            ]))

        elif nframe == 8:
            door_pos = 45<<2
            cocotb.start_soon(async_run_all([
                # Turn on VINF (cmd 5) mode:
                spi_send_reg(dut, CMD_VOPTS, '1'+'0'+'000', what='VINF on, LEAK_FIXED off, map_mode=0'),
                # Update the door's sliding position:
                spi_send_reg(dut, CMD_DOOR0, door_reg_string(door_x, door_y, door_wall, door_pos), what='Door'),
            ]))

        elif nframe == 9:
            door_pos = 46<<2
            cocotb.start_soon(async_run_all([
                # Set VSHIFT to 15:
                spi_send_reg(dut, CMD_VSHIFT, 15, count=6, what='VSHIFT=15'),
                # Update the door's sliding position:
                spi_send_reg(dut, CMD_DOOR0, door_reg_string(door_x, door_y, door_wall, door_pos), what='Door'),
            ]))

        elif nframe == 10:
            door_pos = 47<<2
            cocotb.start_soon(async_run_all([
                # Enable LEAK_FIXED:
                spi_send_reg(dut, CMD_VOPTS, '1'+'1'+'000', what='VINF on, LEAK_FIXED on, map_mode=0'),
                # Update the door's sliding position:
                spi_send_reg(dut, CMD_DOOR0, door_reg_string(door_x, door_y, door_wall, door_pos), what='Door'),
            ]))

        elif nframe == 11:
            door_pos = 48<<2
            cocotb.start_soon(async_run_all([
                # Turn off VINF and LEAK_FIXED:
                spi_send_reg(dut, CMD_VOPTS, '0'+'0'+'000', what='VINF off, LEAK_FIXED off, map_mode=0'),
                # Update the door's sliding position:
                spi_send_reg(dut, CMD_DOOR0, door_reg_string(door_x, door_y, door_wall, door_pos), what='Door'),
            ]))

        elif nframe == 12:
            # Turn on generated textures (disable SPI textures; done with dut.gen_texb.value = 0 in IMMEDIATE inputs, below)...
            door_x += 1
            door_pos = 49<<2
            cocotb.start_soon(async_run_all([
                # ...AND map_mode=2:
                spi_send_reg(dut, CMD_VOPTS, '0'+'0'+'010', what='VINF off, LEAK_FIXED off, map_mode=2'),
                # Update the door sliding position:
                spi_send_reg(dut, CMD_DOOR0, door_reg_string(door_x, door_y, door_wall, door_pos), what='Door'),
                # Also change the map rectangle regs:
                spi_send_reg(dut, CMD_MAPR,
                    '000110' + '000100' +   # mapr_ax/y = 6,4
                    '011110' + '001010' +   # mapr_bx/y = 30,10
                    '0' +                   # mapr_erase (off)
                    '010',                  # mapr_wall
                    what='Map rectangle'
                ),
            ]))

        elif nframe == 13:
            # Turn off generated textures (enable SPI textures again; dut.gen_texb.value = 1 in IMMEDIATE inputs, below)...
            # door_pos = 255
            cocotb.start_soon(async_run_all([
                # ...AND reset floor leak:
                # Send SPI2 ('reg') command 2 (LEAK) and payload 0:
                spi_send_reg(dut, CMD_LEAK, 0, count=6, what='LEAK=0'),
                # # Update the door sliding position:
                # spi_send_reg(dut, CMD_DOOR0, door_reg_string(door_x, door_y, door_wall, door_pos), what='Door'),
            ]))

        elif nframe == 14:
            door_pos = 255
            cocotb.start_soon(async_run_all([
                # Set MapDivX/Y to 12,3 with wall IDs 7,0:
                spi_send_reg(dut, CMD_MAPD, '001100'+'000010'+'111'+'000', what='MDX/Y=12,3 WX/Y=7,0'),
                # Update the door sliding position:
                spi_send_reg(dut, CMD_DOOR0, door_reg_string(door_x, door_y, door_wall, door_pos), what='Door'),
            ]))

        elif nframe == 15:
            # Reset VSHIFT:
            cocotb.start_soon(spi_send_reg(dut, CMD_VSHIFT, 0, count=6, what='VSHIFT=0'))

        elif nframe == 16:
            # Set TEXADD6 to 30:
            cocotb.start_soon(spi_send_reg(dut, CMD_TEXADD6, 30, count=24, what='TEXADD6=30')) # NOTE: TEXADD6 is for wallID 7...
            
        elif nframe == 17:
            # Set TEXADD7 to 10:
            cocotb.start_soon(spi_send_reg(dut, CMD_TEXADD7, 10, count=24, what='TEXADD7=30')) # NOTE: ...TEXADD7 is for wallID 0.


        # Now handle IMMEDIATE inputs that take effect on the current frame,
        # rather than the next...
        if DEMO_MODE:
            pass

        # GENERATED TEXTURES:
        elif frame == 0:
            # Turn on gen_tex (disable texture ROM; use generated textures instead):
            set_gen_texb(dut, 0)
            # dut.gen_texb.value = 0 #NOTE: Immediate, so takes effect ON frame 0, not 1.

        # EXTERNAL TEXTURES:
        elif frame == 1:
            # Turn off gen_tex (enable texture ROM):
            set_gen_texb(dut, 1)
            # dut.gen_texb.value = 1 #NOTE: Immediate, so takes effect ON frame 1.

        # GENERATED TEXTURES:
        elif frame == 12:
            # Turn on gen_tex (disable texture ROM; use generated textures instead):
            set_gen_texb(dut, 0)
            # dut.gen_texb.value = 0 #NOTE: Immediate, so takes effect ON frame 12.

        # EXTERNAL TEXTURES:
        elif frame == 13:
            # Turn off gen_tex (enable texture ROM):
            set_gen_texb(dut, 1)
            # dut.gen_texb.value = 1 #NOTE: Immediate, so takes effect ON frame 13.

        # Create PPM file to visualise the frame, and write its header:
        img = open(f"frames_out/frame-{frame:03d}.ppm", "w")
        img.write("P3\n")
        img.write(f"{int(hrange*hres)} {vrange:d}\n")
        img.write("255\n")

        for n in range(vrange): # 525 lines * however many frames in frame_count
            print(f"Rendering line {n} of frame {frame}")
            for n in range(int(hrange*hres)): # 800 pixel clocks per line.
                if n % 100 == 0:
                    print('.', end='')
                if 'x' in str(dut.rgb.value).lower():
                    # Output is unknown; make it green:
                    r = 0
                    g = 255
                    b = 0
                elif 'z' in str(dut.rgb.value).lower():
                    # Output is HiZ; make it magenta:
                    r = 255
                    g = 0
                    b = 255
                else:
                    rr = int(dut.rr.value)
                    gg = int(dut.gg.value)
                    bb = int(dut.bb.value)
                    hsyncb = 255 if str(dut.hsync_n.value).lower()=='x' else (0==dut.hsync_n.value)*0b110000
                    vsyncb = 128 if str(dut.vsync_n.value).lower()=='x' else (0==dut.vsync_n.value)*0b110000
                    r = (rr << 6) | hsyncb
                    g = (gg << 6) | vsyncb
                    b = (bb << 6)
                sample_count += 1
                if 'x' in (str(dut.rgb.value) + str(dut.hsync_n.value) + str(dut.vsync_n.value)).lower():
                    x_count += 1
                if 'z' in (str(dut.rgb.value) + str(dut.hsync_n.value) + str(dut.vsync_n.value)).lower():
                    z_count += 1
                img.write(f"{r} {g} {b}\n")
                if HIGH_RES is None:
                    await ClockCycles(dut.clk, 1) 
                else:
                    await Timer(CLOCK_PERIOD/hres, unit='ns')
        img.close()
        render_stop_time = time.time()
        delta = render_stop_time - render_start_time
        print(f"[{render_stop_time}: Frame simulated in {delta} seconds]")
    print("Waiting 1 more clock, for start of next line...")
    await ClockCycles(dut.clk, 1)

    print(f"DONE: Out of {sample_count} pixels/samples, got: {x_count} 'x'; {z_count} 'z'")


    # # Start up
    # await start_up(dut)

    # logger.info("Running the test...")

    # # Wait for some time...
    # await ClockCycles(dut.clk, 10)

    # # Please note that cocotb cannpt write to individual bits of a vector.
    # # If you need to write to individual bits, you can separate e.g. the 
    # # bidir_PAD vector into individual bits through a tb wrapper.
    # # Even better, use individual pad names for each bit.

    # # # Start the counter by setting all inputs to 1
    # # dut.input_PAD.value = -1

    # # Wait for a number of clock cycles
    # await ClockCycles(dut.clk, 100)

    # # # Check the end result of the counter
    # # assert dut.bidir_PAD.value == 100 - 1

    # logger.info("Done!")



def chip_top_runner():

    proj_path = Path(__file__).resolve().parent

    sources = []
    defines = {f"SLOT_{slot.upper()}": True}
    includes = [proj_path / "../src/"]

    # Set the LibreLane PDK/SCL/PAD defines
    defines[f"PDK_{pdk.replace('-','_')}"] = True
    defines[f"SCL_{scl}"] = True
    defines[f"PAD_{pad}"] = True
    defines[f"SRAM_{sram}"] = True

    if gl:
        # SCL models
        sources.append(Path(pdk_root) / pdk / "libs.ref" / scl / "verilog" / f"{scl}.v")
        if scl != "gf180mcu_as_sc_mcu7t3v3":
            sources.append(Path(pdk_root) / pdk / "libs.ref" / scl / "verilog" / "primitives.v")

        # We use the powered netlist
        # sources.append(proj_path / f"../final/pnl/{hdl_toplevel}.pnl.v")
        # sources.append(proj_path / "../chip_top_dummy.pnl.v")
        sources.append(proj_path / "../final/pnl/chip_top.pnl.v")
        sources.append(proj_path / "../src/generated_defines.svh")
        sources.append(proj_path / "../src/slot_defines.svh")
        sources.append(proj_path / "texture_rom/W25Q128JVxIM.v")
        sources.append(proj_path / "chip_top_wrapper.v")

        defines.update({"FUNCTIONAL": True, "USE_POWER_PINS": True})
    else:
        sources.append(proj_path / "../src/chip_top.sv")
        sources.append(proj_path / "../src/rbz_options.v")
        sources.append(proj_path / "../src/raybox-zero/src/rtl/fixed_point_params.v")
        sources.append(proj_path / "../src/raybox-zero/src/rtl/helpers.v")
        sources.append(proj_path / "../src/raybox-zero/src/rtl/doors.v")
        sources.append(proj_path / "../src/raybox-zero/src/rtl/rbzero.v")
        sources.append(proj_path / "../src/raybox-zero/src/rtl/spi_registers.v")
        sources.append(proj_path / "../src/raybox-zero/src/rtl/debug_overlay.v")
        sources.append(proj_path / "../src/raybox-zero/src/rtl/map_overlay.v")
        sources.append(proj_path / "../src/raybox-zero/src/rtl/map_rom.v")
        sources.append(proj_path / "../src/raybox-zero/src/rtl/lzc.v")
        sources.append(proj_path / "../src/raybox-zero/src/rtl/reciprocal.v")
        sources.append(proj_path / "../src/raybox-zero/src/rtl/wall_tracer.v")
        sources.append(proj_path / "../src/raybox-zero/src/rtl/row_render.v")
        sources.append(proj_path / "../src/raybox-zero/src/rtl/vga_mux.v")
        sources.append(proj_path / "../src/raybox-zero/src/rtl/vga_sync.v")
        sources.append(proj_path / "../src/chip_core.sv")
        sources.append(proj_path / "texture_rom/W25Q128JVxIM.v")
        sources.append(proj_path / "chip_top_wrapper.v")

    sources += [
        # IO pad models
        Path(pdk_root) / pdk / f"libs.ref/{pad}/verilog/{pad}.v",
        
        # # SRAM macros
        # Path(pdk_root) / pdk / f"libs.ref/{sram}/verilog/{sram}__sram512x8m8wm1.v",
        
        # Custom IP
        proj_path / "../ip/gf180mcu_ws_ip__logo/vh/gf180mcu_ws_ip__logo.v",
        proj_path / "../ip/gf180mcu_ws_ip__marker/vh/gf180mcu_ws_ip__marker.v",
        proj_path / "../ip/gf180mcu_ws_ip__qrcode_id/vh/gf180mcu_ws_ip__qrcode_id.v",
        proj_path / "../ip/gf180mcu_ws_ip__shuttle_id/vh/gf180mcu_ws_ip__shuttle_id.v",
        proj_path / "../ip/gf180mcu_ws_ip__project_id/vh/gf180mcu_ws_ip__project_id.v",
        
    ]

    build_args = []

    if sim == "icarus":
        # For debugging
        # build_args = ["-Winfloop", "-pfileline=1"]
        pass

    if sim == "verilator":
        build_args = ["--timing", "--trace", "--trace-fst", "--trace-structs"]

    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel=hdl_toplevel,
        defines=defines,
        always=True,
        includes=includes,
        build_args=build_args,
        waves=True,
    )

    plusargs = []

    runner.test(
        hdl_toplevel=hdl_toplevel,
        test_module="chip_top_tb,",
        plusargs=plusargs,
        waves=True,
    )


if __name__ == "__main__":
    chip_top_runner()
