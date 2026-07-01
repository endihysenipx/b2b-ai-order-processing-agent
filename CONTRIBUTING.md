# Contributing

Development follows a simple `main` and `develop` workflow.

- `main` represents mentor-reviewable work.
- `develop` collects completed feature branches.
- Feature branches use names such as `feature/project-foundation`, `feature/orders-api`, and `feature/frontend-layout`.
- Pull requests should reference a Week 3 issue or project-board card.
- Do not commit secrets or real customer data.
- Run backend and frontend tests before requesting review.

## Local Checks

```bash
cd backend
ruff check .
pytest

cd ../frontend
npm run lint
npm test
npm run build
```
