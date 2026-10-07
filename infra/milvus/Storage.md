**Причины падения базы данных надо смотреть в логах контейнеров и в состоянии Docker**, а не в traceback Python: там только «не достучался до `:19530`», без объяснения, **почему** процесс упал.

## 1. Логи Milvus-стека (главное)

Полный прогон метрик этапа 4: `powershell -File scripts/stage4_eval/run_all.ps1` (Milvus поднимается внутри `run_infra.ps1`). Снимок логов **не** делается на каждый запуск — только при сбое или с флагом `-SnapshotMilvusLogs`.

**Экспорт в папку** (из корня репозитория; снимок в `infra/milvus/logs/<дата-время>/`):

```powershell
python scripts/start_milvus_logs.py
python scripts/start_milvus_logs.py --since 6h
python scripts/start_milvus_logs.py --tail 500
```

В каталоге снимка: `compose-ps.txt`, `milvus-standalone.log`, `milvus-etcd.log`, `milvus-minio.log`, `inspect-state.txt` (OOMKilled, exit code), `README.txt`. Папка `infra/milvus/logs/` в `.gitignore` — в Git не коммитится.

Ручные команды — каталог compose `infra\milvus`:

```powershell
cd X:\Учеба_УИИ\Итоговы_Проект\infra\milvus

docker compose ps -a
```

Имена контейнеров у вас в `docker-compose.yml`: **`milvus-standalone`**, **`milvus-etcd`**, **`milvus-minio`**. Падение любого из них часто роняет поиск.

**Сразу после сбоя** (или во время «затыка» на 24-м вопросе):

```powershell
docker logs milvus-standalone --tail 200
docker logs milvus-etcd --tail 100
docker logs milvus-minio --tail 100
```

С меткой времени и в файл (удобно для отчёта):

```powershell
docker logs milvus-standalone --timestamps --since 2h 2>&1 | Out-File -Encoding utf8 milvus-standalone.log
docker logs milvus-etcd       --timestamps --since 2h 2>&1 | Out-File -Encoding utf8 milvus-etcd.log
docker logs milvus-minio      --timestamps --since 2h 2>&1 | Out-File -Encoding utf8 milvus-minio.log
```

Через compose (сервис в файле называется `standalone`):

```powershell
docker compose logs standalone --tail 200
docker compose logs etcd minio --tail 100
```

В `Readme1.md` для отладки уже указано: `docker-compose logs -f milvus-standalone` и ожидание `Welcome to Milvus!`.

**На что смотреть в тексте:**

- `OOM`, `killed`, `out of memory`, `cannot allocate memory`
- `panic`, `fatal`, `segmentation fault`
- ошибки etcd/minio: `connection refused`, `backend`, `quota`, `no space`
- резкий **exit** контейнера без явной ошибки в логе Milvus → часто **OOM Killer** со стороны Docker/WSL2

## 2. Убили ли контейнер из‑за памяти (OOM)

```powershell
docker inspect milvus-standalone --format "{{.State.Status}} {{.State.ExitCode}} {{.State.OOMKilled}} {{.State.FinishedAt}}"
docker inspect milvus-etcd --format "{{.State.OOMKilled}} {{.State.ExitCode}}"
docker inspect milvus-minio --format "{{.State.OOMKilled}} {{.State.ExitCode}}"
```

Если **`OOMKilled=true`** — не «битая БД», а **не хватило RAM** у Docker VM / хоста (типично при Milvus + Ollama + долгий eval на Windows).

Полная картина состояния:

```powershell
docker inspect milvus-standalone
```

(секции `State`, `RestartCount`).

## 3. События Docker (кто и когда остановился)

В отдельном окне **до** прогона метрик:

```powershell
docker events --filter container=milvus-standalone --filter container=milvus-etcd --filter container=milvus-minio
```

Будут строки `die`, `oom`, `kill` с временем — можно сопоставить с **23-й (timeout)** / **24-й (Milvus)**.

## 4. Ресурсы в момент падения

Пока eval идёт, в другом терминале:

```powershell
docker stats --no-stream
```

Смотрите **MEM %** у `milvus-standalone`, `milvus-etcd`, `milvus-minio` и контейнера **ollama**.

На хосте: **Диспетчер задач** → память; **Docker Desktop** → Settings → Resources (лимит RAM для WSL2).

## 5. Что **не** даст причину смерти БД

- Traceback **pymilvus** в терминале eval — только клиент (`Connection refused`, 75 retries).
- **`stage4_gen_eval_results.json`** — поле `error`, без логов сервера.
- **`timed out` на 23-м** — это чаще **Ollama** (`timeout_sec: 120`), а Milvus мог умереть **после** или **параллельно**; время смотрите в логах с `--since`.

## 6. Как поймать причину «в следующий раз»

1. Перед `eval_rag_generation --mode live` — `docker compose ps` (все **Up**, standalone **healthy**).
2. Второй терминал: `docker events` или периодически `docker compose ps -a`.
3. После первого `Connection refused` — **сразу** `python scripts/start_milvus_logs.py` (или ручные `docker logs` ниже); при необходимости скопировать снимок в `Этапы/Reports/etap4/` для отчёта.

## 7. Docker Desktop (если в логах контейнера пусто)

**Troubleshoot** → **Get support** / экспорт диагностики, или логи WSL: иногда видно, что **вся VM** перезапустилась — тогда все порты `refused` одновременно.

---

## Скрипты проекта

| Скрипт | Назначение |
|--------|------------|
| `scripts/start_milvus.py` | `docker compose up -d` в `infra/milvus` |
| `scripts/start_milvus_logs.py` | Снимок логов и состояния контейнеров в `infra/milvus/logs/<дата-время>/` |

Подробнее по этапу 4 (eval, `--start-id`): `scripts/stage4_eval/README.md`.

**Итог:** логи **есть** — **`start_milvus_logs.py`** или **`docker logs`** по трём контейнерам + **`OOMKilled`** в `inspect-state.txt`. Traceback pymilvus в eval — только симптом (`Connection refused`); типичная причина при длинном live-прогоне — **нехватка RAM / падение standalone или etcd/minio под Docker Desktop**, а не повреждение векторов в коллекции.