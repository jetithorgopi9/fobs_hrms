<div align="center">
	<img src="hrms.png" height="80px" width="80px" alt="FOBS Logo">
	<h2>FOBS</h2>
	<p>Open-source, modern, and easy-to-use HR and payroll software.</p>
</div>

<div align="center">
	<img src=".github/hrms-hero.png" alt="FOBS HR and Payroll">
</div>

## FOBS

FOBS is an HR and payroll management system for handling employee lifecycle, leave and attendance, expense claims, performance management, payroll, taxation, and mobile-first HR workflows from one place.

Repository: [jetithorgopi9/fobs_hrms](https://github.com/jetithorgopi9/fobs_hrms)

## Key Features

- **Employee Lifecycle**: Manage onboarding, employee records, promotions, transfers, feedback, and exit processes.
- **Leave and Attendance**: Configure leave policies, holidays, check-ins, attendance, leave balances, and attendance reports.
- **Expense Claims and Advances**: Manage employee advances, expense claims, and approval workflows.
- **Performance Management**: Track goals, KRAs, self-evaluations, appraisals, and review cycles.
- **Payroll and Taxation**: Create salary structures, run payroll, manage income tax slabs, salary slips, additional salaries, and off-cycle payments.
- **Mobile HR Workflows**: Apply for and approve leaves, check in and out, and access employee details on the go.

<details open>
<summary>View Screenshots</summary>

<img src=".github/hrms-appraisal.png" alt="FOBS appraisal">
<img src=".github/hrms-requisition.png" alt="FOBS requisition">
<img src=".github/hrms-attendance.png" alt="FOBS attendance">
<img src=".github/hrms-salary.png" alt="FOBS salary">
<img src=".github/hrms-pwa.png" alt="FOBS mobile app">

</details>

## Technology

- **Frappe Framework**: Full-stack web application framework written in Python and JavaScript.
- **Frappe UI**: Vue-based UI components for modern single-page application interfaces.
- **ERPNext compatibility**: Accounting and payroll-related workflows can integrate with ERPNext where configured.

## Docker Development Setup

You need Docker, Docker Compose, and Git installed.

```sh
git clone -b develop https://github.com/jetithorgopi9/fobs_hrms.git
cd fobs_hrms/docker
docker compose -p fobs_hrms up -d
```

After the setup script creates the site, open:

```text
http://localhost:8000
```

Default login:

- Username: `Administrator`
- Password: `admin`

## VPS Deployment Without Affecting Existing Docker Sites

Use a separate directory, a separate Docker Compose project name, and localhost-only ports. This prevents container names, networks, volumes, and public ports from colliding with the three Docker sites already running on the VPS.

Recommended isolation choices:

- Compose project name: `fobs_hrms`
- Host app port: `127.0.0.1:18000`
- Host socket port: `127.0.0.1:19000`
- Docker volume prefix: created automatically from the project name

### Install on VPS

```sh
cd /opt
sudo git clone -b develop https://github.com/jetithorgopi9/fobs_hrms.git fobs_hrms
sudo chown -R "$USER":"$USER" /opt/fobs_hrms
cd /opt/fobs_hrms/docker
```

Create a VPS override file so the app does not bind to ports already used by production sites:

```sh
cat > docker-compose.vps.yml <<'EOF'
services:
  mariadb:
    environment:
      MYSQL_ROOT_PASSWORD: change_this_strong_root_password

  frappe:
    ports:
      - "127.0.0.1:18000:8000"
      - "127.0.0.1:19000:9000"
EOF
```

Start only the FOBS stack:

```sh
docker compose -p fobs_hrms -f docker-compose.yml -f docker-compose.vps.yml up -d
```

Check status and logs:

```sh
docker compose -p fobs_hrms -f docker-compose.yml -f docker-compose.vps.yml ps
docker compose -p fobs_hrms -f docker-compose.yml -f docker-compose.vps.yml logs -f frappe
```

Open locally on the VPS:

```text
http://127.0.0.1:18000
```

### Connect Domain Through Existing Reverse Proxy

Point a subdomain such as `fobs.example.com` to the VPS, then proxy it to `127.0.0.1:18000` from your existing Nginx, Caddy, Traefik, or Apache setup.

Example Nginx server block:

```nginx
server {
    listen 80;
    server_name fobs.example.com;

    location / {
        proxy_pass http://127.0.0.1:18000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Reload Nginx after testing the config:

```sh
sudo nginx -t
sudo systemctl reload nginx
```

### Safe Operations

Stop only FOBS:

```sh
docker compose -p fobs_hrms -f docker-compose.yml -f docker-compose.vps.yml stop
```

Restart only FOBS:

```sh
docker compose -p fobs_hrms -f docker-compose.yml -f docker-compose.vps.yml restart
```

Update only FOBS:

```sh
cd /opt/fobs_hrms
git pull origin develop
cd docker
docker compose -p fobs_hrms -f docker-compose.yml -f docker-compose.vps.yml pull
docker compose -p fobs_hrms -f docker-compose.yml -f docker-compose.vps.yml up -d
```

Remove only FOBS containers and network, keeping the database volume:

```sh
docker compose -p fobs_hrms -f docker-compose.yml -f docker-compose.vps.yml down
```

Do not run `docker compose down` from another project directory, and do not run broad cleanup commands such as `docker system prune -a` on a production VPS unless you have confirmed every running site and backup.

## Important Production Notes

The bundled Docker setup is development-oriented. Before using FOBS as a production HR/payroll system, change default passwords, add HTTPS, configure backups, review email settings, and consider moving to a hardened production Frappe deployment.

## License

This project follows the license included in this repository.
