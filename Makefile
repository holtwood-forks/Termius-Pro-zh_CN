PYTHON ?= python3
.PHONY: doctor status status-json verify verify-json patch patch-trial patch-skip check report report-trial report-skip restore

status:
	$(PYTHON) tools/status.py

status-json:
	$(PYTHON) tools/status.py --json

verify:
	$(PYTHON) tools/verify_asar.py

verify-json:
	$(PYTHON) tools/verify_asar.py --json

doctor:
	$(PYTHON) tools/status.py
	$(PYTHON) tools/verify_asar.py
	$(PYTHON) tools/lint_rules.py rules
	$(PYTHON) -m pytest -q

patch:
	$(PYTHON) fontlang.py -l

patch-trial:
	$(PYTHON) fontlang.py -lt

patch-skip:
	$(PYTHON) fontlang.py -lk

check:
	$(PYTHON) tools/lint_rules.py rules
	$(PYTHON) -m pytest -q

report:
	$(PYTHON) tools/report_rules.py

report-trial:
	$(PYTHON) tools/report_rules.py -t

report-skip:
	$(PYTHON) tools/report_rules.py -k

restore:
	$(PYTHON) tools/restore.py
