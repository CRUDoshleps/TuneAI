# Production monitoring

The production host runs a small, isolated observability stack:

- Grafana, exposed only through Caddy at `https://tuneai.vnshk.ru/monitoring/`;
- Prometheus with 15-day and 2 GB retention limits;
- node-exporter for host CPU, memory, disk and network;
- cAdvisor for TuneAI container CPU and memory;
- blackbox-exporter for external readiness and latency checks.

Prometheus and exporters do not publish host ports. Grafana requires its own
login and persists data in named Docker volumes. The generated initial admin
password is stored only on the VM at
`/srv/monitoring/secrets/grafana_admin_password` with mode `0600`.

Install or update the stack from a checked-out release:

```bash
sudo deploy/monitoring/install.sh
```

Validate it:

```bash
sudo docker compose -f /srv/monitoring/compose.yaml ps
curl --fail https://tuneai.vnshk.ru/monitoring/api/health
```

Retrieve the initial password through an authorized SSH session and change it
after the first Grafana login:

```bash
sudo cat /srv/monitoring/secrets/grafana_admin_password
```

The existing `tuneai-health.timer` checks the external Grafana health endpoint
and all five monitoring containers every minute, in addition to the application
readiness and AI checks.
