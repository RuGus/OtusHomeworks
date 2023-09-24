# 05_HTTP_SERVER

## Simple http server

### Архитектура

Веб-сервер, частично реализующий протокол HTTP.
Реализация с использованием threading.

### Запуск
>
>python httpd.py

### Выполнение тестов

При запущенном сервере:
>
>python httptest.py

### Результат нагрузочного тестирования

wrk -t 5 -c 400 -d 5  <http://localhost:8080/>
>Running 5s test @ <http://localhost:8080/>
> 5 threads and 400 connections
> Thread Stats   Avg      Stdev     Max   +/- Stdev
> Latency    23.09ms  142.57ms   1.87s    96.97%
> Req/Sec     1.73k     1.07k    6.09k    67.56%
> 39201 requests in 5.01s, 6.43MB read
> Socket errors: connect 0, read 39198, write 0, timeout 10
>Requests/sec:   7830.73
>Transfer/sec:      1.28MB

wrk -t 20 -c 1000 -d 15  <http://localhost:8080/>
>Running 15s test @ <http://localhost:8080/>
> 20 threads and 1000 connections
> Thread Stats   Avg      Stdev     Max   +/- Stdev
> Latency     6.87ms   64.83ms   1.86s    98.81%
> Req/Sec   666.04    591.36     3.51k    69.51%
> 119631 requests in 15.10s, 19.62MB read
> Socket errors: connect 0, read 119625, write 0, timeout 26
>Requests/sec:   7924.66
>Transfer/sec:      1.30MB
