@echo off
REM Скрипт запуска Attu UI для Milvus
REM Attu - веб-интерфейс для управления и мониторинга Milvus

docker run -d --name milvus-attu -p 3000:3000 -e MILVUS_URL=http://milvus-standalone:19530 --network milvus zilliz/attu:v2.4.0

echo Attu UI запущен на http://localhost:3000
