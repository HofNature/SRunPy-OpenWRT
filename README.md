# 校园网自动登陆器（深澜网关专用）OpenWRT 版

### 支持的功能

1. 记住账号和密码
2. 开机自动启动
3. 断线自动重连
4. 命令行操作

### 使用说明

要安装 OpenWRT 版 SRunPy，请按照以下步骤操作：

下载 `srunpy-1.0.0.ipk` 和 `luci-app-srunpy-1.0.0.ipk` 包，下载地址：[GitHub Releases](https://github.com/HofNature/SRunPy-OpenWRT/releases)。

#### LuCI Web 界面
1. 进入 OpenWRT 设备的 LuCI Web 界面。

2. 进入 `系统` > `软件包`。

3. 点击 `上传软件包`，然后选择你下载的 `srunpy-1.0.0.ipk` 和 `luci-app-srunpy-1.0.0.ipk` 文件。

4. 点击 `上传` 将软件包上传到设备。

5. 软件包上传完成后，点击 `安装` 进行安装。

6. 安装完成后，你可以通过 LuCI Web 界面的 `服务` > `SRunPy` 进行配置。

#### 命令行安装

1. 将下载的软件包传输到你的 OpenWRT 设备。你可以使用 `scp` 或其他文件传输方法。

2. SSH 登录到你的 OpenWRT 设备，并导航到你传输软件包的目录。

3. 使用以下命令安装软件包：
    ```sh
    opkg install srunpy-1.0.0.ipk
    opkg install luci-app-srunpy-1.0.0.ipk
    ```

4. 安装完成后，你可以通过 LuCI Web 界面或直接编辑配置文件来配置 SRunPy。

### 命令行使用

你也可以直接从命令行操作脚本。以下是一些常用命令：

- 启动脚本：
    ```sh
    srunpy --host <host> --protcol <protocol> --username <username> --password <password> --sleeptime <sleeptime> --ssl_verify <true/false>
    ```

### 待办事项

1. 添加更多配置选项
2. 改进错误处理

### 测试学校

1. 北京航空航天大学（BUAA）沙河校区

### 致谢

该程序基于 [iskoldt/srunauthenticator](https://github.com/iskoldt-X/SRUN-authenticator) 的后端开发。

# SRunPy for OpenWRT

### Supported Features

1. Remember account and password
2. Auto start on boot
3. Auto reconnect on disconnection
4. Operate from command line

### Usage Instructions

To install SRunPy for OpenWRT, follow these steps:

Download the `srunpy-1.0.0.ipk` and `luci-app-srunpy-1.0.0.ipk` packages from the [GitHub Releases](https://github.com/HofNature/SRunPy-OpenWRT/releases).

#### LuCI Web Interface
1. Navigate to the LuCI web interface of your OpenWRT device.

2. Go to `System` > `Software`.

3. Click on `Upload Package`, then select the `srunpy-1.0.0.ipk` and `luci-app-srunpy-1.0.0.ipk` files you downloaded.

4. Click `Upload` to upload the packages to your device.

5. Once the packages are uploaded, click `Install` to install them.

6. After installation, you can configure SRunPy through the LuCI web interface under `Services` > `SRunPy`.

#### Command Line Installation

1. Transfer the downloaded packages to your OpenWRT device. You can use `scp` or any other file transfer method.

2. SSH into your OpenWRT device and navigate to the directory where you transferred the packages.

3. Install the packages using the following commands:
    ```sh
    opkg install srunpy-1.0.0.ipk
    opkg install luci-app-srunpy-1.0.0.ipk
    ```

4. After installation, you can configure SRunPy through the LuCI web interface or by editing the configuration files directly.

### Command Line Usage

You can also operate the script directly from the command line. Here are some common commands:

- Start the script:
    ```sh
    srunpy --host <host> --protcol <protocol> --username <username> --password <password> --sleeptime <sleeptime> --ssl_verify <true/false>
    ```

### TODO

1. Add more configuration options
2. Improve error handling

### Tested Schools

1. Beijing University of Aeronautics and Astronautics (BUAA) Shahe Campus

### Acknowledgements

This program is based on [iskoldt/srunauthenticator](https://github.com/iskoldt-X/SRUN-authenticator) for the backend.