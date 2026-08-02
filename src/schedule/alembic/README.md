# Alembic

Based on [Async alembic configuration with ruff post-hook](https://gist.github.com/dantetemplar/cbef8b9f1d9d6cde7547629d6d85fcd1) gist.

### Autogenerate migration
```bash
alembic revision --autogenerate -m "<some message>"
```
### Upgrade database
Upgrade to the latest revision
```bash
alembic upgrade head
```
Upgrade to the specific revision
```bash
alembic upgrade <revision>
```

### Skip migration but apply it in database

Stamp will set the database alembic version to the specified revision but will not change schema.
```bash
alembic stamp <revision>
```
