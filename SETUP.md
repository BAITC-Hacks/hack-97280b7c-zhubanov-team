# Подготовка к HackAlem AI

## Запуск

В PowerShell из этой папки:

```powershell
.\.venv\Scripts\Activate.ps1
jupyter lab
```

Откройте `hackathon_ready.ipynb` и выберите kernel `Python (HackAlem)`.

## Что уже установлено

Проверены и доступны: `numpy`, `pandas`, `requests`, `python-dotenv`, `pydantic`, `openai`, `ipykernel`.

## Дозагрузка полного стека

Если на ноутбуке достаточно свободной памяти и стабильный интернет:

```powershell
python -m pip install -r requirements.txt
```

## API-ключи

Не вставляйте ключи в `.ipynb` и не коммитьте `.env`. Перед запуском можно задать переменные окружения:

```powershell
$env:OPENAI_API_KEY = "ваш-ключ"
$env:NVIDIA_API_KEY = "ваш-ключ"
```

