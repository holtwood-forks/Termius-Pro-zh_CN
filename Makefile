.PHONY: doctor status status-json verify verify-json patch patch-trial patch-skip check report report-trial report-skip restore

status:
	python tools/status.py

status-json:
	python tools/status.py --json

verify:
	python tools/verify_asar.py

verify-json:
	python tools/verify_asar.py --json

doctor:
	python tools/status.py
	python tools/verify_asar.py
	python tools/lint_rules.py rules
	python -m pytest -q

patch:
	python fontlang.py -l

patch-trial:
	python fontlang.py -lt

patch-skip:
	python fontlang.py -lk

check:
	python tools/lint_rules.py rules
	python -m pytest -q

report:
	python tools/report_rules.py

report-trial:
	python tools/report_rules.py -t

report-skip:
	python tools/report_rules.py -k

restore:
	python tools/restore.py
