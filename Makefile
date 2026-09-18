.PHONY: schemas test lint templates

schemas:
	python3 scripts/fetch_bpmn_schemas.py

templates:
	python3 scripts/build_templates.py

test:
	pytest -v

lint:
	npm run lint

