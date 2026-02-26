# Billing Contest

Сервис управления платежами по заказам на FastAPI.

Поддерживает:
- типы платежей `cash` и `acquiring`;
- операции `deposit` и `refund`;
- хранение в реляционной БД (по умолчанию SQLite);
- синхронизацию acquiring-платежей со внешним API банка.


## 1. Запуск

```bash
docker compose up -d --build
```

API:
- `http://localhost:8000`

## 2. Переменные окружения

`docker-compose.yaml` поддерживает следующие переменные:

- `APP_PORT` (по умолчанию `8000`)
- `DATABASE_URL` (по умолчанию `sqlite:////app/data/billing.db`)
- `BANK_API_BASE_URL` (по умолчанию `https://bank.api`)
- `BANK_API_TIMEOUT_SECONDS` (по умолчанию `5.0`)


Пример запуска с кастомным банком:

```bash
BANK_API_BASE_URL=http://host.docker.internal:8081 docker compose up -d --build
```

## 3. REST API

- `GET /orders` - список заказов с платежами
- `GET /orders/{order_id}` - получить заказ по id
- `POST /orders/{order_id}/payments` - создать платеж (`deposit`)
- `POST /payments/{payment_id}/refund` - сделать возврат (`refund`)
- `POST /payments/{payment_id}/sync` - синхронизировать acquiring-платеж с банком
- `POST /payments/reconcile` - массовая синхронизация pending acquiring-платежей

Пример тела запроса на создание платежа:

```json
{
  "amount": "150.00",
  "payment_type": "acquiring"
}
```

## 4. Важное по acquiring

Для `acquiring` операций сервис обращается во внешний банк (`BANK_API_BASE_URL`).
Если API банка недоступен, операции acquiring будут завершаться ошибкой интеграции.
