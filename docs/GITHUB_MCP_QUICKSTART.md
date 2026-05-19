# GitHub MCP Server — Quick Start

Get the GitHub MCP Server talking to VS Code Copilot in **5 minutes**.

---

## Prerequisites

| Requirement | Check |
|-------------|-------|
| VS Code 1.99 or later | `code --version` |
| Docker Desktop running | `docker ps` |
| GitHub account | — |
| VS Code Copilot Chat extension | Extensions → search "Copilot Chat" |

---

## Step 1 — Create a GitHub Personal Access Token (PAT)

1. Open GitHub → **Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token**.
2. Set a name (e.g., `github-mcp-local`) and expiration (90 days is a good
   starting point).
3. Under **Repository access**, choose "All repositories" or select specific
   repos you want the agent to read/write.
4. Grant these permissions:
   - **Contents** — Read and write
   - **Issues** — Read and write
   - **Pull requests** — Read and write
   - **Metadata** — Read (mandatory)
5. Copy the token. You will not see it again.

> **Security note** — VS Code stores the token in its secret store (encrypted).
> It is never written to disk and never committed to source control.

---

## Step 2 — Add the server to `.vscode/mcp.json`

If the file does not exist yet, create it. Otherwise, add the `github` block
inside `servers`:

```jsonc
{
  "servers": {
    "github": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
        "ghcr.io/github/github-mcp-server"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${input:github_pat}"
      }
    }
  },
  "inputs": [
    {
      "id": "github_pat",
      "type": "promptString",
      "description": "GitHub Personal Access Token",
      "password": true
    }
  ]
}
```

> **npx alternative** — if you prefer not to use Docker:
> ```jsonc
> "command": "npx",
> "args": ["-y", "@modelcontextprotocol/server-github"]
> ```
> Requires Node.js 18+.

---

## Step 3 — Reload VS Code and enter your PAT

1. Open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`).
2. Run **Developer: Reload Window**.
3. When Copilot next needs the GitHub MCP Server it will prompt for your PAT.
   Paste the token and press Enter. It is stored for the session.

---

## Step 4 — Verify it works

Open Copilot Chat in **Agent mode** and try these prompts:

```
List the last 5 open issues in <owner>/<repo>
```

```
Show me the contents of README.md from the main branch of <owner>/<repo>
```

```
Search for the word "TODO" in the src/ directory of <owner>/<repo>
```

If the agent calls `list_issues`, `get_file_contents`, or `search_code` and
returns real data, the server is working.

---

## Common commands you can use right away

| Goal | Prompt template |
|------|----------------|
| List open issues | `List all open issues in <owner>/<repo>` |
| Get a specific issue | `Read issue #<N> in <owner>/<repo>` |
| Search code | `Search for "<pattern>" in <owner>/<repo>` |
| Read a file | `Show me <path> from the main branch of <owner>/<repo>` |
| Summarise a PR | `Summarise PR #<N> in <owner>/<repo>` |
| Create an issue | `Create a GitHub issue in <owner>/<repo> titled "<title>" with body "<body>"` |
| List recent commits | `List the last 10 commits on main in <owner>/<repo>` |

---

## Troubleshooting

**Server not listed in Copilot tools**
- Confirm Docker Desktop is running: `docker ps`
- Pull the image: `docker pull ghcr.io/github/github-mcp-server`
- Reload VS Code

**PAT prompt never appears / PAT rejected**
- Ensure `"password": true` is set on the input in `mcp.json`
- Confirm the PAT has not expired (GitHub → Settings → Developer settings)
- Check that the PAT has `Contents: Read and write` and `Metadata: Read`

**"Resource not accessible by personal access token"**
- Fine-grained PATs need explicit repository access — set "All repositories"
  or grant access to the specific repo you are querying

**Rate limits**
- GitHub REST API allows 5 000 requests/hour per PAT for authenticated users
- For heavy automation (hundreds of issues), space operations out or use a
  GitHub App token instead of a PAT

---

## Next steps

| Resource | Description |
|----------|-------------|
| [GITHUB_MCP_USECASES.md](./GITHUB_MCP_USECASES.md) | 20+ real-world use cases with ready-to-paste prompts |
| [GITHUB_MCP_INTEGRATION.md](./GITHUB_MCP_INTEGRATION.md) | Full AAF + GitHub MCP integration guide |
| [MCP_SERVER.md](./MCP_SERVER.md) | AAF MCP Server tool reference |
