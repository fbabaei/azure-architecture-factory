# Application Zone — CaseWright Quick Start Guide

A new user's complete journey from setup to invoking agents through the Application Zone multi-tenant workspace.

---

## **Part 1: Prerequisites & Setup** (10 minutes)

### What You Need
- Python 3.9+ (for Application Zone backend)
- Node.js 18+ (optional, for testing Teams Bot)
- A running **CaseWright** instance (port 8000)
- Two terminal windows

### Step 1: Start the Application Zone Backend

The backend serves agent discovery and runtime proxy APIs on **port 5000**.

```pwsh
# From azure-architecture-factory root
cd demo

# Activate venv if not already active
..\.venv\Scripts\Activate.ps1

# Start the backend
python app.py --port 5000
```

**Expected output:**
```
 * Running on http://127.0.0.1:5000
 * Serving Flask app 'app'
```

### Step 2: Open the Factory Portal

The portal UI runs on **port 5501** and provides the Application Zone workspace interface.

In your browser, navigate to:
```
http://127.0.0.1:5501/factory-portal.html#application-zone-workspace
```

**Expected:** You'll see the **Application Zone Workspace** tab with a blue "Create Instance" button.

---

## **Part 2: Create Your First Instance** (2 minutes)

### What Quick Launch (Local) is for

**Quick Launch (Local)** is a portal-side test harness for trying an App Pack without doing a real Azure deployment. Use it to validate the selected pack/version, check required inputs, create a local/in-memory instance record, discover available agents, and test runtime or sample agent calls.

It is intended for catalog validation, demos, and developer testing before promotion to a real deployment path. It is **not** the production deployment experience.

An **instance** is your isolated workspace for a single app (e.g., CaseWright). It holds agent definitions and configuration.

### Step 3: Click "Create Instance"

1. In the portal, click **Create Instance** (blue button)
2. You'll see a form with fields:
   - **Instance Name** → Enter `my-casewright`
   - **App ID** → Enter `casewright`
   - **Runtime URL** (optional) → Enter `http://localhost:8000` if CaseWright is running

3. Click **Create**

**Expected response:**
```
✅ Instance created: my-casewright
- Agent definitions loaded from manifest
- 6 agents available
- Ready to discover and invoke
```

The instance will show:
- Instance ID (for reference)
- 6 agents ready to use
- 4 supporting services

---

## **Part 3: Load and Inspect Agents** (3 minutes)

Your instance now contains all CaseWright agents. Let's see them in action.

### Step 4: Click "Load Agents"

Once your instance is created, you'll see:
- **Available Agents** section
- A dropdown listing all discovered agents by use case

The agents are organized by category:

#### **Knowledge Agents** (Chat & Retrieval)
1. **Case Knowledge Agent (Agentic RAG)**
   - Use case: Case summarization, policy lookup, document retrieval
   - Capability: AI-powered grounded chat with citations
   - Endpoint: `POST /api/chat/query`

2. **Case Chat Agent (Fallback)**
   - Use case: Quick answers, offline fallback
   - Capability: Direct RAG without Foundry orchestration
   - Endpoint: `POST /api/chat`

#### **Discovery Agents** (SharePoint & Site Listing)
3. **SharePoint Discovery Agent**
   - Use case: Find accessible sites and members
   - Endpoint: `GET /api/sharepoint/sites`

4. **SharePoint Sync Agent**
   - Use case: Trigger document sync with delta detection
   - Endpoint: `POST /api/sharepoint/sites/sync`

#### **Operations Agents** (System Health)
5. **Health Agent**
   - Use case: Check service health and readiness
   - Endpoint: `GET /api/health`

#### **Pipeline Agents** (Indexing & Search)
6. **Indexer Agent**
   - Use case: Manage and monitor Azure AI Search indexing
   - Endpoint: `GET /api/pipeline/indexer-status`

---

## **Part 4: Invoke an Agent** (5 minutes)

Now let's actually call an agent and see it in action.

### Step 5: Select an Agent

From the **Agent Selector** dropdown, choose:
```
Case Knowledge Agent (Agentic RAG) - AI-powered case and policy assistant
```

### Step 6: Prepare the Payload

Each agent expects specific input. For the Case Knowledge Agent, the payload is:

```json
{
  "query": "What are the key dispute factors in this case?",
  "user_id": "alice@contoso.com",
  "session_id": "conv-20260630-session-1",
  "chat_history": [],
  "filters": {}
}
```

**How to enter it:**
1. Click in the **Agent Payload** text area
2. Clear any existing content
3. Paste the JSON above (or use the pre-filled example)

**Payload field descriptions:**
- `query` (required) — Your question about cases or policies
- `user_id` (required) — Identifier for conversation history tracking
- `session_id` (required) — Unique conversation ID
- `chat_history` (optional) — Prior turns for context (array of turn objects)
- `filters` (optional) — Search filters (e.g., by document type, date range)

### Step 7: Invoke the Agent

Click **Invoke Selected Agent**

**What happens behind the scenes:**
1. Portal sends request to Application Zone backend (port 5000)
2. Backend reads the runtime connection (http://localhost:8000)
3. Backend proxies the request to CaseWright API
4. CaseWright processes the query and returns results
5. Results display in the **Agent Output** panel

**Expected response (if CaseWright is running):**
```json
{
  "answer": "The key dispute factors in the Northwind v. Contoso case include...",
  "citations": [
    {
      "title": "northwind-v-contoso.md",
      "source": "https://storage.azure.com/.../northwind-v-contoso.md",
      "snippet": "The primary claims relate to..."
    }
  ],
  "document_count": 3,
  "session_id": "conv-20260630-session-1"
}
```

**If CaseWright is not running:**
```
Error: Instance is not connected to a runtime
```
This is **expected** — see Setup Troubleshooting below.

---

## **Part 5: Other Agents & Operations** (2 minutes each)

### Test the Health Agent
Payload:
```json
{}
```
Response: `{"status": "ok", "service": "casewright-api"}`

### Test the Indexer Agent (Get Status)
Payload:
```json
{
  "indexer_name": "casewright-multimodal-indexer"
}
```
Response: Indexer execution status, document count, last run time

### Test SharePoint Discovery
Payload:
```json
{}
```
Response: List of SharePoint sites accessible to the service

### Test SharePoint Sync (Trigger Sync)
Payload:
```json
{
  "site_id": "contoso.sharepoint.com/sites/legal",
  "force": false
}
```
Response: Sync job queued, returns job ID

---

## **Part 6: Using Other Channels** (Optional)

The agents can also be accessed through other frontends:

### Web Chat UI
If you have CaseWright running:
```
http://localhost:8000/
```
→ Static HTML chat client for quick testing

### Microsoft Teams Bot
For Teams integration:
```pwsh
cd casewright/frontend/teams-bot

# Install M365 Agents Playground
winget install --id Microsoft.M365AgentsPlayground

# Start the Teams bot dev server
npm run dev:teamsfx

# In another terminal, launch Playground
agentsplayground -e http://localhost:3978/api/messages -c msteams
```
→ Test Teams bot without a Teams tenant

---

## **Common Workflows**

### Workflow 1: Ask a Question About Cases
1. Create instance pointing to CaseWright runtime
2. Select **Case Knowledge Agent (Agentic RAG)**
3. Enter query in payload
4. View answer with citations

### Workflow 2: Sync New Documents from SharePoint
1. Create instance
2. Select **SharePoint Sync Agent**
3. Provide site_id in payload
4. Monitor sync progress via **Indexer Agent** status

### Workflow 3: Check System Health
1. Create instance
2. Select **Health Agent**
3. Send empty payload `{}`
4. View service status

### Workflow 4: Multi-Turn Conversation
1. Make first query to **Case Knowledge Agent**
2. Copy `session_id` from response
3. Make second query with same `session_id` and add first turn to `chat_history`
4. Agent uses context from previous turns

---

## **Setup Troubleshooting**

| Issue | Cause | Solution |
|-------|-------|----------|
| Portal won't load | Factory portal not running | Run `python scripts/start_factory_portal.py` |
| "Cannot connect to backend" | Application Zone backend not running | Run `python demo/app.py --port 5000` |
| "Instance not connected to runtime" | CaseWright not running on port 8000 | Start CaseWright: `uvicorn casewright.api.main:app --port 8000` |
| Agent dropdown empty | Manifest not loading | Check browser console for JSON errors; verify manifest path in instance creation |
| Payload rejected | Invalid JSON | Paste valid JSON; use provided examples |
| Slow response | Network latency | Ensure all services (5000, 5501, 8000) are on same machine or network |

---

## **Architecture at a Glance**

```
┌─────────────────────────────────────────────────────┐
│         Factory Portal (port 5501)                  │
│     - Create instances                              │
│     - Select agents                                 │
│     - Build payloads                                │
│     - View responses                                │
└──────────────────┬──────────────────────────────────┘
                   │ HTTP
                   ↓
┌─────────────────────────────────────────────────────┐
│   Application Zone Backend (port 5000)              │
│     - Agent discovery (reads manifest)              │
│     - Runtime proxy (forwards to CaseWright)        │
│     - Instance management                           │
└──────────────────┬──────────────────────────────────┘
                   │ HTTP (proxy)
                   ↓
┌─────────────────────────────────────────────────────┐
│      CaseWright Runtime (port 8000)                 │
│     - /api/chat/query (agentic RAG)                 │
│     - /api/sharepoint/* (discovery & sync)          │
│     - /api/pipeline/* (indexing)                    │
│     - /api/health (liveness)                        │
└─────────────────────────────────────────────────────┘
```

---

## **What's Next?**

### For Developers
- Modify agent metadata in `factory-templates/application-zone/packs/casewright/1.0.0/manifest.json`
- Add new agents by adding routers to `casewright/src/casewright/api/routers/`
- Extend backend proxy in `demo/app.py`

### For End Users
- Use Teams Bot or Web Chat UI for daily case lookups
- Create instances for different projects/teams
- Save and share instance configurations

### For DevOps
- Deploy CaseWright to Azure Container Apps
- Deploy Application Zone backend to App Service or Container Apps
- Deploy factory portal as static site to Storage + CDN
- Configure instance runtime URLs for production endpoints

---

## **Support & Documentation**

- **CaseWright API** → [casewright/README.md](../../casewright/README.md)
- **Application Zone Manifest** → [manifest.json](packs/casewright/1.0.0/manifest.json)
- **Backend Code** → [demo/app.py](../../demo/app.py)
- **Portal Code** → [factory-portal.html](../../factory-portal.html)

Questions? Check browser console for detailed error messages.
