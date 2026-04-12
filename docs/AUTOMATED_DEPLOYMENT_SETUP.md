# Automated Deployment Setup Guide (with Tailscale)

This guide shows how to set up secure automatic deployment from GitHub Actions to your server using Tailscale VPN.

## Overview

**Workflow:**
1. Push code to GitHub main branch
2. GitHub Actions builds Docker image (automatic)
3. GitHub Actions pushes image to registry (automatic)
4. GitHub Actions connects to Tailscale VPN (automatic)
5. GitHub Actions deploys via SSH over Tailscale (automatic) ← **Secure!**

**Total time:** ~3-4 minutes from push to deployed

## Why Tailscale?

**Security benefits:**
- ✅ SSH never exposed to public internet
- ✅ Server only accessible via private Tailscale network
- ✅ GitHub Actions temporarily joins network during deployment
- ✅ No firewall rules needed for deployment
- ✅ Encrypted WireGuard VPN tunnel

**vs Traditional SSH:**
- ❌ Traditional: SSH port 22 exposed to internet (attack surface)
- ✅ Tailscale: SSH only accessible via private VPN

## Prerequisites

- Server with Docker installed
- Backend already deployed once manually (see DEPLOY.md)
- Tailscale account (free tier works: https://tailscale.com)
- GitHub repository access

## Step 1: Set Up Tailscale

### 1.1: Install Tailscale on Your Server

```bash
# SSH to your server
ssh your-user@your-server

# Install Tailscale (Ubuntu/Debian)
curl -fsSL https://tailscale.com/install.sh | sh

# Start Tailscale and authenticate
sudo tailscale up

# This will show a URL - open it in your browser to authenticate
# Choose your Tailscale account and approve the device
```

### 1.2: Get Server's Tailscale IP

```bash
# On your server
tailscale ip -4

# Example output: 100.64.1.2
# Save this IP - you'll need it for GitHub secrets
```

### 1.3: Create OAuth Client for GitHub Actions

1. Go to: https://login.tailscale.com/admin/settings/oauth
2. Click **Generate OAuth client**
3. Set the following:
   - **Description**: GitHub Actions Deploy
   - **Tags**: `tag:ci` (create if doesn't exist)
   - **Scopes**: Leave default or select minimal needed scopes
4. Click **Generate client**
5. **Save both values** (you won't see them again):
   - **OAuth client ID**: `tskey-client-...`
   - **OAuth client secret**: `tskey-...`

### 1.4: Configure Server ACLs (Access Control)

1. Go to: https://login.tailscale.com/admin/acls
2. Add a tag for CI in the ACL file:

```json
{
  "tagOwners": {
    "tag:ci": ["your-email@example.com"]
  },
  "acls": [
    {
      "action": "accept",
      "src": ["tag:ci"],
      "dst": ["*:22"]
    }
  ]
}
```

This allows devices with `tag:ci` (GitHub Actions) to SSH to your servers.

3. Click **Save**

### 1.5: Disable SSH on Public Internet (Optional but Recommended)

Since you're using Tailscale, you can disable public SSH:

```bash
# On your server
# Edit SSH config
sudo nano /etc/ssh/sshd_config

# Change this line:
# Port 22
# To:
Port 2222  # Or any other port

# Or better: only listen on Tailscale interface
# Add this line:
ListenAddress 100.64.1.2  # Your Tailscale IP

# Restart SSH
sudo systemctl restart sshd
```

**Important:** Test you can still SSH via Tailscale before closing your current session!

## Step 2: Generate SSH Key for GitHub Actions

On your **local machine** (not the server):

```bash
# Generate new SSH key pair specifically for GitHub Actions
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/github_actions_deploy

# This creates:
# - ~/.ssh/github_actions_deploy (private key)
# - ~/.ssh/github_actions_deploy.pub (public key)
```

**Important:** Use a **different key** than your personal SSH key for security.

## Step 2: Add Public Key to Server

Copy the public key to your server:

```bash
# Display public key
cat ~/.ssh/github_actions_deploy.pub

# Copy the output, then SSH to your server
ssh your-user@your-server

# Add public key to authorized_keys
echo "YOUR_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys

# Set correct permissions
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh

# Exit server
exit
```

**Test the key works:**
```bash
ssh -i ~/.ssh/github_actions_deploy your-user@your-server
# Should login without password
```

## Step 3: Add Secrets to GitHub

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add the following secrets:

### `TS_OAUTH_CLIENT_ID`
- Name: `TS_OAUTH_CLIENT_ID`
- Value: The OAuth client ID from Step 1.3 (starts with `tskey-client-`)

### `TS_OAUTH_SECRET`
- Name: `TS_OAUTH_SECRET`
- Value: The OAuth client secret from Step 1.3 (starts with `tskey-`)

### `TAILSCALE_SERVER_IP`
- Name: `TAILSCALE_SERVER_IP`
- Value: Your server's Tailscale IP from Step 1.2 (e.g., `100.64.1.2`)

### `SSH_PRIVATE_KEY`
```bash
# Display private key
cat ~/.ssh/github_actions_deploy

# Copy the ENTIRE output including:
# -----BEGIN OPENSSH PRIVATE KEY-----
# ...
# -----END OPENSSH PRIVATE KEY-----
```
- Name: `SSH_PRIVATE_KEY`
- Value: Paste the entire private key

### `SERVER_USER`
- Name: `SERVER_USER`
- Value: Your SSH username (e.g., `ubuntu`, `root`, or your username)

## Step 4: Verify Secrets

Your GitHub Secrets should look like:
```
TS_OAUTH_CLIENT_ID     ********  (Tailscale OAuth client ID)
TS_OAUTH_SECRET        ********  (Tailscale OAuth secret)
TAILSCALE_SERVER_IP    ********  (Server Tailscale IP)
SSH_PRIVATE_KEY        ********  (Private key content)
SERVER_USER            ********  (Your SSH username)
```

## Step 5: Test Deployment

**Option 1: Push a change**
```bash
# Make a small change (e.g., add a comment to backend code)
echo "# Test deployment" >> backend/app/main.py

git add .
git commit -m "test: trigger auto-deployment"
git push
```

**Option 2: Manual trigger**
1. Go to: https://github.com/FredrikMeyer/codex/actions
2. Click "Deploy to Production"
3. Click "Run workflow"
4. Select branch: `main`
5. Click "Run workflow"

## Step 6: Monitor Deployment

Watch the deployment:
1. Go to: https://github.com/FredrikMeyer/codex/actions
2. Click on the latest "Deploy to Production" workflow
3. Watch the steps execute:
   - ✅ Deploy to server via SSH
   - ✅ Pull latest image
   - ✅ Restart with new image
   - ✅ Show status

**Expected output:**
```
cd /var/www/codex/backend
docker compose -f docker-compose.prod.yml pull
[main] Pulling
[main] Pulled
docker compose -f docker-compose.prod.yml up -d
[main] Container asthma-backend  Started
docker compose -f docker-compose.prod.yml ps
NAME              IMAGE                                    STATUS
asthma-backend    ghcr.io/fredrikmeyer/codex/backend:latest Up 2 seconds (healthy)
✅ Deployment complete!
```

## How It Works

### Workflow Trigger
```yaml
on:
  workflow_run:
    workflows: ["Build and Publish Docker Image"]
    types:
      - completed
```

The deployment workflow triggers **after** the build workflow completes successfully.

### Deployment Steps
1. **Connect to Tailscale** using OAuth credentials
   - GitHub Actions runner joins your Tailscale network temporarily
   - Gets assigned a Tailscale IP with `tag:ci`
2. **SSH into server** via Tailscale IP (private network)
   - Uses private key from secrets
   - Connection encrypted by WireGuard (Tailscale's VPN)
3. **Navigate** to `/var/www/codex/backend`
4. **Pull latest image** from GitHub Container Registry
5. **Restart container** with new image
6. **Show status** and recent logs
7. **Disconnect from Tailscale** (automatic cleanup)

### Security (Tailscale Advantages)
- ✅ **SSH never exposed to internet** - Only accessible via Tailscale VPN
- ✅ **Encrypted WireGuard tunnel** - All traffic encrypted
- ✅ **Temporary access** - GitHub Actions disconnects after deployment
- ✅ **Access control** - Server ACLs control what `tag:ci` can access
- ✅ **Audit trail** - Tailscale logs all connections
- ✅ **SSH key** - Still used for authentication (defense in depth)
- ✅ **Limited permissions** - Only deployment commands
- ✅ **No firewall rules** - Tailscale handles routing

## Workflow Files

### `.github/workflows/docker-publish.yml`
- Builds Docker image
- Pushes to GitHub Container Registry
- Triggers deployment workflow

### `.github/workflows/deploy.yml`
- Waits for build to complete
- SSH to server
- Deploys latest image

## Complete Deployment Flow

```
┌─────────────────┐
│ Push to GitHub  │
└────────┬────────┘
         ↓
┌──────────────────────────────────┐
│ Build & Publish (2-3 min)        │
│ - Build Docker image             │
│ - Run tests                      │
│ - Push to ghcr.io               │
└────────┬─────────────────────────┘
         ↓ (triggers)
┌──────────────────────────────────┐
│ Deploy via Tailscale (30 sec)    │
│ 1. Connect to Tailscale VPN      │
│ 2. SSH to server (via Tailscale) │
│ 3. Pull latest image             │
│ 4. Restart container             │
│ 5. Disconnect from Tailscale     │
└────────┬─────────────────────────┘
         ↓
┌──────────────────────────────────┐
│        Your Server               │
│  ┌────────────────────┐          │
│  │  Tailscale Network │          │
│  │  (Private VPN)     │          │
│  │                    │          │
│  │  [Docker Container]│          │
│  └────────────────────┘          │
│                                  │
│  SSH: Only via Tailscale         │
│  Public SSH: Disabled ✅         │
└──────────────────────────────────┘
         ↓
    ✅ Deployed Securely!
```

**Total time:** ~3-4 minutes from push to production
**Security:** SSH never exposed to public internet

## Manual Deployment (Fallback)

If automatic deployment fails, you can always deploy manually:

```bash
# SSH to server
ssh your-user@your-server

# Deploy manually
cd /var/www/codex/backend
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Deployment Fails: Permission Denied

**Problem:** SSH key doesn't have permission

**Solution:**
1. Check public key is in server's `~/.ssh/authorized_keys`
2. Verify permissions: `chmod 600 ~/.ssh/authorized_keys`
3. Test key manually: `ssh -i ~/.ssh/github_actions_deploy user@server`

### Deployment Fails: Docker Commands Fail

**Problem:** User doesn't have Docker permissions

**Solution:**
```bash
# On server
sudo usermod -aG docker $USER

# Logout and login for group to take effect
exit
ssh your-user@your-server

# Verify
docker ps
```

### Deployment Fails: Directory Not Found

**Problem:** `/var/www/codex/backend` doesn't exist

**Solution:**
```bash
# Create directory with correct ownership
sudo mkdir -p /var/www/codex/backend
sudo chown -R $USER:$USER /var/www/codex

# Deploy manually once to set up structure
cd /var/www/codex/backend
curl -O https://raw.githubusercontent.com/FredrikMeyer/codex/main/backend/docker-compose.prod.yml
```

### Check Deployment Logs

```bash
# On server
cd /var/www/codex/backend
docker compose -f docker-compose.prod.yml logs --tail=50
```

### View GitHub Actions Logs

1. Go to: https://github.com/FredrikMeyer/codex/actions
2. Click on failed workflow
3. Click on failed step
4. View error message

## Security Best Practices

### ✅ Do's
- Use separate SSH key for GitHub Actions
- Store private key in GitHub Secrets only
- Limit key permissions (no root access if possible)
- Rotate keys periodically
- Review deployment logs

### ❌ Don'ts
- Don't commit private keys to repository
- Don't use personal SSH key for automation
- Don't give root access unless necessary
- Don't store secrets in code or environment files

## Advanced: Notifications

Add Slack/Discord notifications on deployment:

```yaml
- name: Notify on success
  if: success()
  run: |
    curl -X POST YOUR_WEBHOOK_URL \
      -H 'Content-Type: application/json' \
      -d '{"text":"✅ Backend deployed successfully"}'

- name: Notify on failure
  if: failure()
  run: |
    curl -X POST YOUR_WEBHOOK_URL \
      -H 'Content-Type: application/json' \
      -d '{"text":"❌ Backend deployment failed"}'
```

## Alternative: Watchtower (Auto-Pull)

Instead of SSH deployment, use Watchtower to auto-pull images:

```yaml
# Add to docker-compose.prod.yml
services:
  watchtower:
    image: containrrr/watchtower
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --interval 300  # Check every 5 minutes
```

**Pros:** No SSH needed, simpler
**Cons:** Less control, delayed updates (polls every N minutes)

## Summary

✅ **Automated deployment workflow created**
✅ **SSH-based deployment via GitHub Actions**
✅ **Secure secret management**
✅ **Triggers after successful build**
✅ **Manual trigger option available**
✅ **Complete deployment in ~3-4 minutes**

**Your new workflow:**
1. `git push` → Done!
2. Wait 3-4 minutes
3. Changes live in production

**No more manual server SSH!** 🚀
