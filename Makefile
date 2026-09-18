.PHONY: schemas test lint

schemas:
	python3 scripts/fetch_bpmn_schemas.py

test:
	pytest -v

lint:
	npm run lint
