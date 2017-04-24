# rqalpha-mod-vnpy
RQAlpha 对接 vnpy 的扩展 Mod。通过启用该 Mod 来实现期货策略的实盘交易。目前本模块仍处在正式发布前的测试阶段，您可以下载参与测试并开 Issue 提交 bug，也欢迎您提交代码，参与开发。  

***本开源模块未进行详尽完备的测试，作者不保证您通过本模块获取到数据的完整以及准确性、不保证您的策略逻辑正确触发对应的实盘操作，您通过使用本模块实盘操作产生的损益与作者无关。***

***当前版本的 rqalpha-mod-vnpy 仅支持 VN.PY 的最新版本，请您及时更新 VN.PY 的代码***

## 环境要求
由于 VN.PY 项目仅支持 Linux 和 Windows 系统，python2.7 环境，目前本模块也仅支持在 Linux 或 Windows 系统下 python2.7 环境。  
作者仅在 ubuntu 16.04 LTS 系统进行了测试。关于 Windows 及其他 Linux 发行版下的兼容性，作者会在精力允许的情况进行测试，也欢迎您将兼容性情况反馈给我。


## 编译和安装

本模块依赖 RQAlpha 和 VN.PY 两个项目，所以需要完成两个项目的安装。

### 安装 RQAlpha
 rqalpha-mod-vnpy 依赖 2.0.X 版本的 RQAlpha，您可以执行如下命令来安装 RQAlpha
 
 ```
 pip install -U rqalpha
 ```

### 安装 VN.PY
 VN.PY 项目未提供 pip 安装包，所以您只能通过下载源代码自行编译的方式进行安装。详细的环境配置和安装说明您可以查看 [VN.PY官方教程](http://www.vnpy.org/pages/tutorial.html) 。
 
### 安装 mod
在您完成 RQAlpha 的安装之后，您可以执行以下命令来安装 mod：

```
rqalpha mod install vnpy
```
之后您可以执行以下命令来启动 mod:

```
rqalpha mod enable vnpy
```
如果您需要关闭或者卸载 mod 您可以执行以下两条命令:

```
rqalpha mod disable vnpy

rqalpha mod uninstall vnpy
```

## 配置项
您需要在配置项中填入 vnpy 相关文件夹的路径及您的 CTP 账号密码等信息，您可以在 [simnow 官网](http://www.simnow.com.cn) 申请实盘模拟账号。  
配置项的使用与 RQAlpha 其他 mod 无异

``` python
"vnpy": {
    # 您需要接入的接口，目前仅支持 CTP
    "gateway_type": "CTP",
    # VN.PY 项目目录下有一个 vn.trader 文件夹，您需要把该文件夹的路径填到此处
    "vn_trader_path": None,
    # 您使用 simnow 模拟交易时可以选择使用24小时服务器，该服务器允许您在收盘时间测试相关 API，如果您需要全天候测试，您需要开启此项。
    "all_day": True,
    # 向 CTP 发送请求对时间间隔，设置过小会导致请求被吞掉
    "query_interval": 2,
    # 以下是您的 CTP 账户信息，由于您需要将密码明文写在配置文件中，您需要注意保护个人隐私。
    "CTP": {
        "userID": "",
        "password": "",
        "brokerID": "9999",
      	"tdAddress": "tcp://180.168.146.187:10030",
      	"mdAddress": "tcp://180.168.146.187:10031",
    },
}
```

## 开箱即用虚拟机

为了让用户能够在最短时间内体验 rqapha-mod-vnpy，免去繁琐的环境配置和接口编译，作者提供了开箱即用的虚拟机镜像。

有关虚拟机镜像的导入以及 rqalpha 的调试和运行，您可以参考 [rqalpha 文档](http://rqalpha.readthedocs.io/zh_CN/latest/intro/virtual_machine.html)。

[点此下载](https://pan.baidu.com/s/1boLqeGB)

### 体验 rqalpha-mod-vnpy

* 双击打开桌面上的 rqalpha_vnpy_test.py 文件，在配置文件对应位置填入您的 simnow userID 和密码

* 打开终端，依次输入如下命令:
```bash
cd ﻿/home/rqalpha_user/桌面

source activate py2

python rqalpha_vnpy_test.py

```




## FAQ
* 为什么策略在初始化期间停滞了几十秒甚至数分钟？   

	*程序在启动前，需要从 CTP 获取 Instrument 和 Commission 等数据，由于下边问题的原因，像 CTP 发送大量请求会占用很长时间。您可以将 log_level 设置成 verbose 来查看详细的回调函数执行情况。未来可能会考虑开放设置是否全量更新 commission 信息以换取更快的启动速度。*

* 为什么在启动之初程序会报出一堆 ImportError？
    
    *这是由于新版本的 VN.PY 在启动之初会进行接口完整性的自检，若您只编译了 CTP 接口就会导致 VN.PY 抛出异常，一般情况下这并不会影响程序的运行。

* 为什么我在RQAlpha中查询到的账户、持仓信息与我通过快期、vn.trader 等终端查询到的不一致？

	*本 mod 会尽力将您的账户信息恢复至 RQAlpha 中，但由于计算逻辑的不同，可能会导致各个终端显示的数字有差异，另外您通过其他终端下单交易也有可能导致数据同步的不及时。不过这也有可能是程序bug，如果您发现不一致情况严重，欢迎通过Issue的方式向作者提出。*

* VN.PY 的环境配置和安装比较复杂，我搞不定／懒得搞怎么办？

	*作者会尽力研究，争取将VN.PY的安装包含进 mod 中，通过 pip 的形式一键安装，在这之前，作者会提供一个开箱即用虚拟机镜像，供您直接下载使用。*

* 为什么会报 NotImplementedError？

    请尝试将配置文件中的 frequency 设置为 tick。


## TODO

* rqalpha-mod-vnpy 的结构和数据流程图
* 包含 VN.PY 或 vn.trader 的一键部署包
* 接入其他接口
