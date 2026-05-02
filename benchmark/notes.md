
AutoPenBench shipped a now broken Kali Docker container, it has been replaced (`benchmark/machines/kali/Dockerfile`).

Issue #7 reported missing code (wtf)

Add this to `.env`
```
AUTOPENBENCH=$(pwd)/benchmark/auto-pen-bench/benchmark
KALISCRIPTS=$(pwd)/benchmark/auto-pen-bench/benchmark/machines/kali/tmp_script
```

```bash
uv sync --extra bench
cd benchmark/auto-pen-bench
docker-compose -f benchmark/machines/docker-compose.yml build
```


TODO: implement prefetch for AutoPenBench container to reduce benchmark time, at `PentestDriver` initialization images are built from `benchmark` (ex. `in-vitro_access_control_vm0`), this could be a pain in the ass if running the full benchmark with a cloud-hosted vLLM instance paid per time of usage.

