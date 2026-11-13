OUTPUT_FORMAT(elf32-i386)
ENTRY(_start)
SECTIONS {
  . = 0;
  .text : { *(.text.start) *(.text*) *(.rodata*) }
  . = ALIGN(4096);
  __text_end = .;
  .data : { *(.data*) }
  __data_end = .;
  .bss : { *(.bss*) *(COMMON) }
  __bss_end = .;
  /DISCARD/ : { *(.eh_frame*) *(.note*) *(.comment*) }
}
