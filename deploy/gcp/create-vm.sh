#!/usr/bin/env bash
# Creates everything Resolve needs on Google Cloud: a static IP, a firewall rule for
# ports 80/443, and one Ubuntu VM with Docker and 2 GB of swap installed.
# It does not deploy the app; see deploy/PRODUCTION.md for the next steps.
#
# Prerequisites: the gcloud CLI, `gcloud auth login`, a project with billing enabled.
#
#   PROJECT=my-project-id bash deploy/gcp/create-vm.sh
#
# Optional: REGION (default asia-south1), ZONE (default asia-south1-a),
#           MACHINE (default e2-medium: 2 vCPU, 4 GB; the stack needs about 3 GB),
#           DISK_GB (default 40), NAME (default resolve).
set -euo pipefail

: "${PROJECT:?Set PROJECT to your Google Cloud project id}"
REGION="${REGION:-asia-south1}"
ZONE="${ZONE:-${REGION}-a}"
MACHINE="${MACHINE:-e2-medium}"
DISK_GB="${DISK_GB:-40}"
NAME="${NAME:-resolve}"

gcloud config set project "$PROJECT" >/dev/null
gcloud services enable compute.googleapis.com

echo "Reserving a static IP..."
gcloud compute addresses describe "$NAME-ip" --region "$REGION" >/dev/null 2>&1 \
  || gcloud compute addresses create "$NAME-ip" --region "$REGION"
IP="$(gcloud compute addresses describe "$NAME-ip" --region "$REGION" --format='value(address)')"

echo "Opening ports 80 and 443..."
gcloud compute firewall-rules describe "$NAME-web" >/dev/null 2>&1 \
  || gcloud compute firewall-rules create "$NAME-web" \
       --allow tcp:80,tcp:443 --target-tags "$NAME-web" \
       --description "Resolve: HTTP (certificate challenge, redirect) and HTTPS"

STARTUP="$(mktemp)"
cat >"$STARTUP" <<'EOF'
#!/usr/bin/env bash
set -e
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
EOF

echo "Creating the VM ($MACHINE in $ZONE)..."
gcloud compute instances describe "$NAME" --zone "$ZONE" >/dev/null 2>&1 \
  || gcloud compute instances create "$NAME" \
       --zone "$ZONE" --machine-type "$MACHINE" \
       --image-family ubuntu-2404-lts-amd64 --image-project ubuntu-os-cloud \
       --boot-disk-size "${DISK_GB}GB" --boot-disk-type pd-balanced \
       --address "$IP" --tags "$NAME-web" \
       --metadata-from-file startup-script="$STARTUP"
rm -f "$STARTUP"

cat <<EOF

Done. The VM's address is: $IP

Next:
  1. In Cloudflare, add three A records pointing at $IP (DNS only, grey cloud):
       app.<your domain>   auth.<your domain>   mcp.<your domain>
  2. Wait a minute for Docker to install, then connect:
       gcloud compute ssh $NAME --zone $ZONE
  3. On the VM, follow deploy/PRODUCTION.md from "3. Get the code and configure".
EOF
