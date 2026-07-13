current_design $::env(DESIGN_NAME)
set_units -time ns

set clock_port __VIRTUAL_CLK__
if { [info exists ::env(CLOCK_PORT)] } {
    set port_count [llength $::env(CLOCK_PORT)]

    if { $port_count == "0" } {
        puts "\[WARNING] No CLOCK_PORT found. A dummy clock will be used."
    } elseif { $port_count != "1" } {
        puts "\[WARNING] Multi-clock files are not currently supported by the base SDC file. Only the first clock will be constrained."
    }

    if { $port_count > "0" } {
        set ::clock_port [lindex $::env(CLOCK_PORT) 0]
    }
}

if { $::env(CLOCK_PORT) == $::env(CLOCK_NET) } {
    set port_args [get_ports $clock_port]
} else {
    # This should actually use CLOCK_PIN?
    set port_args [get_pins [lindex $::env(CLOCK_NET) 0]]
}

puts "\[INFO] Using clock $clock_port…"
create_clock {*}$port_args -name $clock_port -period $::env(CLOCK_PERIOD)

set input_delay_value [expr $::env(CLOCK_PERIOD) * $::env(IO_DELAY_CONSTRAINT) / 100]
set output_delay_value [expr $::env(CLOCK_PERIOD) * $::env(IO_DELAY_CONSTRAINT) / 100]
puts "\[INFO] Setting output delay to: $output_delay_value"
puts "\[INFO] Setting input delay to: $input_delay_value"

set_max_fanout $::env(MAX_FANOUT_CONSTRAINT) [current_design]
if { [info exists ::env(MAX_TRANSITION_CONSTRAINT)] } {
    set_max_transition $::env(MAX_TRANSITION_CONSTRAINT) [current_design]
}
if { [info exists ::env(MAX_CAPACITANCE_CONSTRAINT)] } {
    set_max_capacitance $::env(MAX_CAPACITANCE_CONSTRAINT) [current_design]
}

set clocks [get_clocks $clock_port]

# Bidirectional pads
set clk_core_inout_ports [get_ports { 
    bidir_PAD[*]
}] 

set_input_delay -min 0 -clock $clocks $clk_core_inout_ports
set_input_delay -max $input_delay_value -clock $clocks $clk_core_inout_ports
set_output_delay $output_delay_value -clock $clocks $clk_core_inout_ports

# Input-only pads
set clk_core_input_ports [get_ports { 
    rst_n_PAD
    input_PAD[*]
}] 

set_input_delay -min 0 -clock $clocks $clk_core_input_ports
set_input_delay -max $input_delay_value -clock $clocks $clk_core_input_ports

# Output load
set cap_load [expr $::env(OUTPUT_CAP_LOAD) / 1000.0]
puts "\[INFO] Setting load to: $cap_load"
set_load $cap_load [all_outputs]

puts "\[INFO] Setting clock uncertainty to: $::env(CLOCK_UNCERTAINTY_CONSTRAINT)"
set_clock_uncertainty $::env(CLOCK_UNCERTAINTY_CONSTRAINT) $clocks

puts "\[INFO] Setting clock transition to: $::env(CLOCK_TRANSITION_CONSTRAINT)"
set_clock_transition $::env(CLOCK_TRANSITION_CONSTRAINT) $clocks

puts "\[INFO] Setting timing derate to: $::env(TIME_DERATING_CONSTRAINT)%"
set_timing_derate -early [expr 1-[expr $::env(TIME_DERATING_CONSTRAINT) / 100]]
set_timing_derate -late [expr 1+[expr $::env(TIME_DERATING_CONSTRAINT) / 100]]

if { [info exists ::env(OPENLANE_SDC_IDEAL_CLOCKS)] && $::env(OPENLANE_SDC_IDEAL_CLOCKS) } {
    unset_propagated_clock [all_clocks]
} else {
    set_propagated_clock [all_clocks]
}


#ANTON: This is an attempt to ignore all timing paths that pass through the reciprocal combo block
# inside rcp_fsm. We assume its outputs are always valid when used.
# set_false_path -through rbzero.wall_tracer.rcp_fsm.*
# set_false_path -through chip_core.rbzero.wall_tracer.rcp_fsm.operand*


set rcp_operand_nets [get_nets -hierarchical {i_chip_core.rbzero.wall_tracer.rcp_fsm.operand*}]

puts "Found [llength $rcp_operand_nets] reciprocal operand nets"

set rcp_op_net_count [llength $rcp_operand_nets]

if {$rcp_op_net_count == 0} {
    error "Could not find reciprocal operand nets"
}

if {$rcp_op_net_count != 22} {
    puts "WARNING: Expected 22 rcp_fsm operand nets, but found $rcp_op_net_count"
}

set_false_path -through $rcp_operand_nets


# set_false_path -through [get_nets -hierarchical {i_chip_core.rbzero.wall_tracer.rcp_fsm.operand*}]
# set_false_path -through rbzero.wall_tracer.rcp_fsm.abs # <= not used; optimised out.
# #ANTON: This specifies that we don't care about timing on these external signals that typically don't change:
# set_false_path -from [get_ports {bidir_PAD[3]}]
# set_false_path -from [get_ports {bidir_PAD[4]}]
# set_false_path -from [get_ports {bidir_PAD[5]}]
# set_false_path -from [get_ports {bidir_PAD[6]}]
# set_false_path -from [get_ports {bidir_PAD[7]}]

#ANTON: This specifies that STA should assume outputs are ALWAYS
# registered. We might still choose to test it with unregistered
# outputs, but if it doesn't work: no worries. Registered is still best :)
set_case_analysis 1 [get_ports {bidir_PAD[6]}]

#ANTON: More stuff that is assumed not to change, typically:
set_case_analysis 0 [get_ports {bidir_PAD[3]}] ; # debug
set_case_analysis 0 [get_ports {bidir_PAD[4]}] ; # inc_px
set_case_analysis 0 [get_ports {bidir_PAD[5]}] ; # inc_py
set_case_analysis 0 [get_ports {bidir_PAD[7]}] ; # tex_pmod_type=>Tiny VGA

# set rcp_launch_regs [get_cells -hierarchical {*rcp_fsm/operand[*]}]

# set rcp_capture_regs [get_cells -hierarchical {*rcp_fsm/o_data[*]}]

# set rcp_launch_q [get_pins -of_objects $rcp_launch_regs -filter {name == Q}]

# set rcp_capture_d [get_pins -of_objects $rcp_capture_regs -filter {name == D}]

# set_multicycle_path 4 -setup \
#     -from $rcp_launch_q \
#     -to   $rcp_capture_d

# set_multicycle_path 3 -hold \
#     -from $rcp_launch_q \
#     -to   $rcp_capture_d
