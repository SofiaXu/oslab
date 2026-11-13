IMPL ?= student
QEMU_DISPLAY ?= gtk
ARGS ?=
PYTHON ?= python3
LABS := 1 2 3 4 5 6 7 8

.DEFAULT_GOAL := help
.PHONY: help doctor prepare student-dist check check-tools all $(foreach n,$(LABS),lab$(n) run-lab$(n) check-lab$(n)) lab2-kernel run-lab2-kernel check-lab2-kernel debug-lab1 debug-lab3 debug-lab5
help:
	@echo 'make doctor | prepare | labN | run-labN | check-labN (N=1..8)'
	@echo 'IMPL=student (default) or reference; QEMU_DISPLAY=gtk or curses; ARGS="..."'
	@echo 'make check IMPL=reference | check-tools | student-dist'
	@echo 'Optional: lab2-kernel | run-lab2-kernel | check-lab2-kernel; debug-lab1/3/5'
doctor prepare student-dist:
	$(PYTHON) tools/oslab.py $@
define LAB_RULES
lab$(1):
	$(PYTHON) tools/oslab.py build $(1) --impl $(IMPL)
run-lab$(1):
	$(PYTHON) tools/oslab.py run $(1) --impl $(IMPL) --display $(QEMU_DISPLAY) --args '$(ARGS)'
check-lab$(1):
	$(PYTHON) tools/oslab.py check $(1) --impl $(IMPL)
endef
$(foreach n,$(LABS),$(eval $(call LAB_RULES,$(n))))
all: $(addprefix lab,$(LABS))
check:
	@set -e; for n in $(LABS); do $(MAKE) --no-print-directory check-lab$$n IMPL=$(IMPL); done
	$(MAKE) --no-print-directory check-tools
check-tools:
	$(PYTHON) -m unittest discover -s tests -p 'test_tools.py' -v
	$(PYTHON) tests/test_qemu.py -v
	$(PYTHON) tests/test_trace.py -v
	OSLAB_IMPL=$(IMPL) $(PYTHON) tests/test_stack_layout.py -v
lab2-kernel:
	$(PYTHON) tools/oslab.py build 9 --impl $(IMPL)
run-lab2-kernel:
	$(PYTHON) tools/oslab.py run 9 --impl $(IMPL) --display $(QEMU_DISPLAY)
check-lab2-kernel:
	$(PYTHON) tools/oslab.py check 9 --impl $(IMPL)
debug-lab1 debug-lab3 debug-lab5:
	$(PYTHON) tools/oslab.py run $(patsubst debug-lab%,%,$@) --impl $(IMPL) --display $(QEMU_DISPLAY) --debug
