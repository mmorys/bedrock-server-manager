# Extra Configuration & Customization

## Color in the CLI:

Bedrock Server Manager's command-line interface (CLI) supports color coding to enhance readability and user experience. This feature might disabled by default on some installs, but you can enable it with the following command:

```bash
pip install colorama
```
---

### No Color Interface:

<div style="text-align: left;">
    <img src="https://raw.githubusercontent.com/DMedina559/bedrock-server-manager/main/docs/images/cli_no_color.png" alt="CLI Menu (No Color)" width="300" height="200">
</div>

### Color Interface:

<div style="text-align: left;">
    <img src="https://raw.githubusercontent.com/DMedina559/bedrock-server-manager/main/docs/images/cli_menu.png" alt="CLI Menu (Color)" width="300" height="200">
</div>

## Custom Web Server Panorama

You can personalize the background panorama displayed on the main web server page.

**Steps:**

1.  Choose your desired background image. It **must** be a JPEG file (with a `.jpeg` extension).
2.  Navigate to the Bedrock Server Manager's configuration directory, typically located at `./.config/` relative to the manager's installation path.
3.  Place your chosen image file into this `./.config/` directory.
4.  Rename the image file to `panorama.jpeg`.
5.  Refresh the web server page in your browser. The new panorama should now be displayed.

**Default Behavior:**

If the file `./.config/panorama.jpeg` is not found or is not a valid JPEG image, the default Bedrock Server Manager icon will be used as the background panorama.

---

## World Icons

The "Servers List" within the web interface can display unique icons for each of your Minecraft worlds, making them easier to identify at a glance.

**How it Works:**

The server manager looks for a file named `world_icon.jpeg` inside each world's specific folder.

**Adding Icons:**

*   **Imported Worlds / Client-Created Worlds:** Worlds that were imported or originally created using the Minecraft client (Bedrock Edition) often already include a `world_icon.jpeg` file within their folder structure. No extra steps may be needed.
*   **Dedicated Server-Created Worlds:** Worlds generated directly by the Bedrock Dedicated Server software usually *do not* have this icon file by default. You can add one manually:
    1.  Obtain or create an image you want to use as the icon (JPEG format, `.jpeg`). A square aspect ratio often looks best.
    2.  Locate the specific world folder for the server you want to customize. This is typically found within the server's directory structure (e.g., `./servers/your_server_name/worlds/your_world_name/`).
    3.  Copy your chosen image file into this specific world folder.
    4.  Rename the image file exactly to `world_icon.jpeg`.
    5.  The icon should appear the next time the server list is loaded or refreshed in the web interface.

**Default Behavior:**

If a `world_icon.jpeg` file is not found within a specific world's directory, the default Bedrock Server Manager icon will be displayed for that world in the server list.

## Home Assistant Integration:
If you use home assistant check out the [bedrock-server-manager integration](https://github.com/DMedina559/bsm-home-assistant-integration)
