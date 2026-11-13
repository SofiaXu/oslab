IMPL ?= student
BUILD_DIR ?= $(CURDIR)/../../build/lab02/$(IMPL)
CC ?= cc
CFLAGS ?= -O2 -g -std=c11 -Wall -Wextra -Wpedantic
ifeq ($(filter $(IMPL),student reference),)
$(error IMPL must be student or reference)
endif
OUTPUT := $(abspath $(BUILD_DIR))/pc
.PHONY: all clean FORCE
all: $(OUTPUT)
$(OUTPUT): $(IMPL)/pc.c Makefile FORCE
	mkdir -p $(dir $@)
	$(CC) $(CPPFLAGS) $(CFLAGS) $< -o $@ $(LDFLAGS) -pthread
clean:
	rm -f $(OUTPUT)
