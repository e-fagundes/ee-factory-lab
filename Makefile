.PHONY: dev-up dev-down dev-logs minikube-start minikube-deploy minikube-status minikube-port-forward minikube-clean test lint validate-examples build-example generate-docs

dev-up:
	docker compose up --build

dev-down:
	docker compose down

dev-logs:
	docker compose logs -f

minikube-start:
	powershell -ExecutionPolicy Bypass -File scripts/setup-minikube.ps1

minikube-deploy:
	powershell -ExecutionPolicy Bypass -File scripts/deploy-minikube.ps1

minikube-status:
	kubectl -n ee-factory-lab get all,pvc

minikube-port-forward:
	powershell -ExecutionPolicy Bypass -File scripts/port-forward.ps1 -StopExisting

minikube-clean:
	kubectl delete -k deploy/minikube --ignore-not-found=true

test:
	cd apps/api && python -m pytest

lint:
	cd apps/api && python -m ruff check app
	cd apps/portal && npm run lint

validate-examples:
	powershell -ExecutionPolicy Bypass -Command "$$env:PYTHONPATH='apps/api'; python -m app.cli.validate_examples"
	powershell -ExecutionPolicy Bypass -Command "$$env:PYTHONPATH='apps/api'; python -m app.cli.scan_examples"

build-example:
	bash scripts/build-example.sh $(EE)

generate-docs:
	powershell -ExecutionPolicy Bypass -Command "$$env:PYTHONPATH='apps/api'; python -m app.cli.generate_docs"
