IMPL ?= student
BUILD_DIR ?= $(CURDIR)/../../build/lab04/$(IMPL)
CC ?= cc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Wpedantic
ifeq ($(filter $(IMPL),student reference),)
$(error IMPL must be student or reference)
endif
.PHONY: all clean FORCE
all: $(BUILD_DIR)/lab04
$(BUILD_DIR)/lab04: $(IMPL)/main.c FORCE
	mkdir -p "$(BUILD_DIR)"
	$(CC) $(CFLAGS) $< -o "$@"
FORCE:
clean:
	rm -f "$(BUILD_DIR)/lab04"
