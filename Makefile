.PHONY: run test docker clean
run:
	python -m uvicorn app.main:app --reload --port 8000
test:
	python -m pytest tests/ -v
docker:
	docker compose up -d --build
clean:
	rm -f *.db *.db-wal *.db-shm
