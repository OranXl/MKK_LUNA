# Асинхронный сервис процессинга платежей

Микросервис для асинхронной обработки платежей с webhook уведомлениями.

## Стек технологий

- **FastAPI** + Pydantic v2 - REST API
- **SQLAlchemy 2.0** (асинхронный режим) - ORM
- **PostgreSQL** - база данных
- **RabbitMQ** (FastStream) - брокер сообщений
- **Alembic** - миграции БД
- **Docker** + docker-compose - контейнеризация

## Архитектура

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Client    │────▶│  FastAPI    │────▶│ PostgreSQL  │
│             │     │    API      │     │             │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  Outbox      │
                    │   Pattern    │
                    └──────────────┘
                           │
                           ▼
                    ┌──────────────┐     ┌─────────────┐
                    │   RabbitMQ   │────▶│  Consumer   │
                    │  payments.new│     │             │
                    └──────────────┘     └─────────────┘
                                                │
                      ┌─────────────────────────┼─────────────────────────┐
                      ▼                         ▼                         ▼
               ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
               │   Process    │         │   Update     │         │   Webhook    │
               │   Payment    │         │    Status    │         │   Notify     │
               │  (2-5 sec)   │         │   in DB      │         │              │
               └──────────────┘         └──────────────┘         └──────────────┘
```

## Компоненты

### API Endpoints

1. **POST /api/v1/payments** - Создание платежа
   - Заголовок: `Idempotency-Key` (обязательный)
   - Заголовок: `X-API-Key` (аутентификация)
   - Body: сумма, валюта, описание, метаданные, webhook_url
   - Ответ: 202 Accepted, payment_id, статус, created_at

2. **GET /api/v1/payments/{payment_id}** - Получение информации о платеже
   - Заголовок: `X-API-Key` (аутентификация)
   - Ответ: детальная информация о платеже

### Consumer

Один обработчик, который:
1. Получает сообщение из очереди `payments.new`
2. Эмулирует обработку платежа (2-5 сек, 90% успех, 10% ошибка)
3. Обновляет статус в БД
4. Отправляет webhook уведомление на указанный URL
5. Реализует повторные попытки при ошибках отправки

### Гарантии доставки

- **Outbox pattern** - гарантированная публикация событий
- **Idempotency key** - защита от дублей
- **Dead Letter Queue** - сообщения после 3 неудачных попыток
- **Retry с экспоненциальной задержкой** - 3 попытки

## Быстрый старт

### Через Docker Compose (рекомендуется)

```bash
# Запуск всех сервисов
docker-compose up -d --build

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

Сервисы будут доступны по адресам:
- API: http://localhost:8000
- PostgreSQL: localhost:5432
- RabbitMQ Management: http://localhost:15672 (guest/guest)
- RabbitMQ AMQP: localhost:5672

### Локальная разработка

1. Установите Poetry (если не установлен):
```bash
curl -sSL https://install.python-poetry.org | python3 -
```

2. Установите зависимости:
```bash
poetry install
```

3. Запустите PostgreSQL и RabbitMQ (через Docker):
```bash
docker-compose up -d postgres rabbitmq
```

4. Примените миграции:
```bash
poetry run alembic upgrade head
```

5. Запустите API:
```bash
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

6. В отдельном терминале запустите consumer:
```bash
poetry run faststream run app.consumer_main:consumer_app
```

**Альтернативно**, можно активировать виртуальное окружение Poetry:
```bash
poetry shell
# Затем запускать команды без префикса "poetry run"
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
faststream run app.consumer_main:consumer_app
```

## Примеры использования

### Создание платежа

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: test-api-key-12345" \
  -H "Idempotency-Key: unique-key-12345" \
  -d '{
    "amount": 1000.00,
    "currency": "RUB",
    "description": "Order payment #12345",
    "metadata": {"order_id": "12345", "user_id": "67890"},
    "webhook_url": "https://webhook.site/your-unique-id"
  }'
```

Ответ:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "amount": "1000.00",
  "currency": "RUB",
  "description": "Order payment #12345",
  "metadata": {"order_id": "12345", "user_id": "67890"},
  "status": "pending",
  "idempotency_key": "unique-key-12345",
  "webhook_url": "https://webhook.site/your-unique-id",
  "created_at": "2024-01-01T12:00:00Z",
  "processed_at": null
}
```

### Получение информации о платеже

```bash
curl http://localhost:8000/api/v1/payments/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: test-api-key-12345"
```

### Проверка здоровья

```bash
curl http://localhost:8000/health
```

## Документация API

После запуска сервиса документация доступна по адресам:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Структура проекта

```
.
├── alembic/                 # Миграции базы данных
│   ├── versions/           # Версии миграций
│   └── env.py
├── app/
│   ├── api/                # API эндпоинты
│   │   └── payments.py
│   ├── consumers/          # RabbitMQ потребители
│   │   └── payment_consumer.py
│   ├── core/               # Конфигурация и утилиты
│   │   ├── config.py
│   │   └── enums.py
│   ├── db/                 # База данных
│   │   └── session.py
│   ├── models/             # SQLAlchemy модели
│   │   └── payment.py
│   ├── schemas/            # Pydantic схемы
│   │   └── payment.py
│   ├── services/           # Бизнес логика
│   │   └── payment.py
│   ├── main.py             # Точка входа API
│   └── consumer_main.py    # Точка входа Consumer
├── alembic.ini
├── docker-compose.yml
├── Dockerfile.api
├── Dockerfile.consumer
├── pyproject.toml
├── poetry.lock
├── README.md
└── TZ.md
```

## Конфигурация

Переменные окружения (можно переопределить через `.env` файл):

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| DATABASE_URL | URL подключения к PostgreSQL | postgresql+asyncpg://postgres:postgres@localhost:5432/payments |
| RABBITMQ_URL | URL подключения к RabbitMQ | amqp://guest:guest@localhost:5672/ |
| API_KEY | Ключ для аутентификации API | test-api-key-12345 |
| MAX_RETRIES | Максимальное количество попыток | 3 |
| RETRY_BASE_DELAY | Базовая задержка между попытками (сек) | 1.0 |

## Особенности реализации

### Outbox Pattern

При создании платежа событие сохраняется в таблицу `outbox_events` в той же транзакции, что и сам платеж. Это гарантирует, что событие не будет потеряно даже при сбое системы.

### Идемпотентность

Использование `Idempotency-Key` в заголовке запроса предотвращает создание дубликатов платежей. При повторном запросе с тем же ключом возвращается существующий платеж.

### Обработка ошибок

- Потребитель автоматически повторяет обработку при ошибках (3 попытки)
- Используется экспоненциальная задержка между попытками
- После исчерпания попыток сообщение попадает в Dead Letter Queue
- Webhook уведомления также имеют механизм повторных попыток

## Лицензия

MIT