---
name: "\U0001F41B Report a Bug"
about: Report an issue in this project
title: "[BUG] [OS_HERE] Quick to the point description of the bug"
labels: bug
assignees: ''

---

---
### **IMPORTANT: Before Submitting**
*   Please search [existing issues](https://github.com/DMedina559/bedrock-server-manager/issues) to ensure this bug hasn't already been reported.
    *   If a similar bug was already reported, please add your additional information or confirm you're experiencing the same issue in that existing thread.
*   If you are using a version prior to the latest release, please try updating first to see if the issue persists.
*   Read the [troubleshooting docs](https://bedrock-server-manager.readthedocs.io/en/latest/general/troubleshooting.html) to see if a workaround or fix has been documented
---

## <sup>(REQUIRED)</sup> **Describe the Bug**:
A clear and concise description of what the bug is.

```text
 # Put text here
```

--- 
### <sup>(REQUIRED)</sup> **To Reproduce**:
Steps to reproduce the behavior:

```text
1. ...
2. ...
3. ...
...

```

---
## <sup>(REQUIRED)</sup> **Expected Behavior**:
A clear and concise description of what you expected to happen.

```text
# Put text here
```

## <sup>(REQUIRED)</sup>**Actual Behavior**:
A clear and concise description of what actually happened.

```text
# Put text here
```

---
### **Environment:**

   <sup>(REQUIRED)</sup> **Operating System & Version**:

<sup>[i.e. Windows 11 Pro 22H2, Ubuntu 22.04 LTS, Debian 12 Bookworm]</sup>

   <sup>(REQUIRED)</sup> **Bedrock Server Manager Version**:

<sup>[i.e. 3.2.4 - can be found in the cli, web UI, and log file]</sup>

   <sup>(REQUIRED)</sup> **Bedrock Server Manager UI**:

<sup>[does the issue happen via CLI (command line interface), via WEB (web ui or HTTP api), or both]</sup>

   <sup>(OPTIONAL)</sup> **Minecraft Bedrock Dedicated Server Version (if relevant)**:

<sup>[i.e. 1.20.50.01]</sup>

   <sup>(OPTIONAL)</sup> **Python Version (if relevant)**:

<sup>[i.e. Python 3.11.4]</sup>

   <sup>(OPTIONAL)</sup> **Browser (if web UI related)**:

<sup>[i.e. Chrome 119, Firefox 118]</sup>

---
### <sup>(REQUIRED)</sup> **Log Files**:
*   **Provide relevant logs from your Bedrock Server Manager log file.**
*   **Paste any relevant logs from log files directly to this issue.** For more extensive logs or full log files please **attach** the relevant log file(s) directly to this issue. If you have multiple files or they are large, please compress them into a `.zip` archive.
*   **Important:** Review logs for any sensitive information before uploading and redact if necessary.
<sub>*   By default, logs are stored in `$BEDROCK_SERVER_MANAGER_DATA_DIR/.logs/`.
<sup>*   The exact path for logs is configured in your `script_config.json` file, which is located in `$BEDROCK_SERVER_MANAGER_DATA_DIR/.config/script_config.json`.</sup>

> [!NOTE]
> *   **Note on Log Level:** Initially, warning/error logs are often sufficient. However, you may be asked to provide more detailed logs by setting the `LOG_LEVEL` in your `script_config.json` to `DEBUG`, reproducing the issue, and then providing the new logs.</sub>

```text
 # Paste logs here
```
---

### <sup>(OPTIONAL)</sup> **`script_config.json` (if relevant)**:
If you believe parts of your `script_config.json` are relevant (e.g., paths, specific settings), please paste the relevant sections here, redacting any sensitive information
```json
{
  // Paste relevant sections here
}
```
---

## <sup>(OPTIONAL)</sup> **Additional Context**:
Add any other context about the problem here that may be relevant. 

```text
 # Put text here
```

---
