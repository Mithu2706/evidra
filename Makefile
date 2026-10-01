.PHONY: install backend frontend dev seed reset test build schemas demo-files

install:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

seed:
	cd backend && python -m app.seed.seed

reset:
	cd backend && python -m app.seed.seed --reset

test:
	cd backend && python -m pytest -q
	cd frontend && npm run typecheck

build:
	cd frontend && npm run build

schemas:
	cd backend && python -m scripts.export_schemas

demo-files:
	cd backend && python -m app.seed.demo_decks ../demo-submissions
