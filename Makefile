SHELL := /bin/bash
.PHONY: test verify evidence-check container-verify container-up container-down
test:
	python3 -m unittest discover -s tests -v
verify: test
	python3 scripts/validate.py --out .runs/latest
evidence-check:
	python3 evidence.py evidence/local
	python3 evidence.py evidence/refresh-20260907
	python3 evidence.py evidence/containers-20260907

container-verify:
	python3 scripts/validate_containers.py --out .runs/container
container-up:
	docker compose up --build --detach --wait
container-down:
	docker compose down
