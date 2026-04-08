# BRD Submission in Chat

You can submit a BRD directly in chat by copy-pasting it.

## Recommended Format

Use this structure so the BRD can be parsed quickly:

```text
Project Name: <name>
Azure Region: <region>
Deploy: scaffold-only | deploy-now

BRD:
<your full BRD text here>
```

## If the BRD Is Long

Send it across multiple messages using part labels:

```text
BRD Part 1/3
...

BRD Part 2/3
...

BRD Part 3/3
...
```

The parts can be combined and processed as one BRD.

## File-Based Option

You can also provide a workspace file path instead of pasting text, for example:

```text
azure-architecture-factory/docs/BRD.md
```

## What Happens Next

After BRD submission, the Azure Architecture Factory flow can:

1. Capture requirements from the BRD.
2. Generate architecture artifacts.
3. Scaffold project assets under `projects/`.
4. Prepare implementation and deployment guidance.
