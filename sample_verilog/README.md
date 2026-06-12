# Sample Verilog Guide

## Compare demo

Upload these two files as one analysis run for V1:

- `pulse_stretcher_v1.v`
- `pulse_stretcher_v1_tb.v`

Upload these two files as another analysis run for V2:

- `pulse_stretcher_v2.v`
- `pulse_stretcher_v2_tb.v`

Both versions implement the same pulse-stretching behavior. V1 uses a countdown counter, while V2 uses a shift register, so the Compare page should have meaningful metric differences to show.

## Error demo

Upload these two files together:

- `broken_adder_8bit.v`
- `broken_adder_8bit_tb.v`

The design compiles, but the testbench intentionally detects a wrong addition result and calls `$fatal`. This is useful for checking that the simulation stage and debug output clearly surface an error.
