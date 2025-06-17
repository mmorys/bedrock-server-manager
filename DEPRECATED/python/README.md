<div style="text-align: center;">
    <img src="https://raw.githubusercontent.com/dmedina559/bedrock-server-manager/main/src/bedrock_server_manager/web/static/image/icon/favicon.svg" alt="Bedrock Server Manager Icon" width="200" height="200">
</div>

**Notice: Deprecation and End of Support**

The contents of this directory represent **legacy versions** of the Bedrock Server Manager and are **no longer maintained or supported.**

# Changelog

### 2.0.0
1. Complete rewrite of script in python
2. Added Windows support
   - Windows support has a few limitations such as:
     - No send-command support
     - No attach to console support
     - Doesn't auto restart if crashed

#### Bash vs Python

The short lived Bedrock Server Manager Bash script is being discontinued and replaced with a new Python-based version. The Bash script was originally designed to support only Debian-based systems, which limited its usability across different operating systems. The bash script will continue to be available but will no longer receive updates.

The switch to python allows cross platform support, standardized processes, and less dependencies. The new script has full feature parity to the bash script

##### To switch to the new version, follow these steps:

- Replace the bash script with the new python script:
  - Follow install instructions above
  - Place the .py file in the same folder as the .sh file
  - Delete the old .sh file if wanted
- Run the script, open the advanced menu then Reconfigure Auto-Update

### 2.0.1

1. Better handle send-command

### 2.0.2

1. Revaluated error codes
2. Ensure write permissions before certain operations such as delete server
