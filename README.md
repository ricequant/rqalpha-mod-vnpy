# rqalpha-mod-vnpy
Rqalpha 对接 vnpy 的扩展 Mod。通过启用该 Mod 来实现期货策略的实盘交易。目前本模块仍处在正式发布前的测试阶段，您可以下载参与测试并开 Issue 提交 bug，也欢迎您提交代码，参与开发。  
***本开源模块未进行详尽完备的测试，作者不保证您通过本模块获取到数据的完整以及准确性、不保证您的策略逻辑正确触发对应的实盘操作，您通过使用本模块实盘操作产生的损益与作者无关。***
## 环境要求
由于 VN.PY 项目仅支持 Linux 和 Windows 系统，python2.7 环境，目前本模块也仅支持在 Linux 或 Windows 系统下 python2.7 环境。  
作者仅在 ubuntu 16.04 LTS 系统进行了测试。关于 Windows 及其他 Linux 发行版下的兼容性，作者会在精力允许的情况进行测试，也欢迎您将兼容性情况反馈给我。


## 编译和安装

本模块依赖 RQAlpha 和 VN.PY 两个项目，所以需要完成两个项目的安装。

### 安装 RQAlpha
 rqalpha-mod-vnpy 依赖 2.0.X 版本的 rqalpha，目前该版本的 rqalpha 仍处于 develop 状态，您可以从 [github](https://github.com/ricequant/rqalpha/) 上克隆代码、checkout 到 develop 分支，并执行 ```pip instal -e .```。  
强烈建议您等到 rqalpha 2.0.X 发布正式版后使用 pip 进行安装。

### 安装 VN.PY
 VN.PY 项目未提供 pip 安装包，所以您只能通过下载源代码自行编译的方式进行安装。详细的环境配置和安装说明您可以查看 [VN.PY官方教程](http://www.vnpy.org/pages/tutorial.html) 。
 
### 安装 mod
在您完成 rqalpha 的安装之后，您可以执行以下命令来安装 mod：

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
配置项的使用与 rqalpha 其他 mod 无异

```
"vnpy": {
	# 您需要接入的接口，目前仅支持 CTP
	"gateway_type": 'CTP',
	# VN.PY 项目目录下有一个 vn.trader 文件夹，您需要把该文件夹的路径填到此处
	"vn_trader_path": None,
	# 您使用 simnow 模拟交易时可以选择使用24小时服务器，该服务器允许您在收盘时间测试相关 API，如果您需要全天候测试，您需要开启此项。   	"all_day": True,
   		# 以下是您的 CTP 账户信息，由于您需要将密码明文写在配置文件中，您需要注意保护个人隐私。   		"CTP": {      		“userID”: “”,                'password': 'c7719950218',                'brokerID': '9999',                'tdAddress': 'tcp://180.168.146.187:10030',                'mdAddress': 'tcp://180.168.146.187:10031'            },
```
## FAQ
* 为什么我在使用过程中会遇到 KeyError 报错，且不能稳定复现？   

	*由于CTP服务器不够稳定，有可能会遇到请求得不到响应的情况，进而影响数据的完整性，数据的不完整有可能会导致程序报错，这一现象在使用 simnow 的时候尤为严重，作者会在后续版本尝试修复这一问题。*
* 为什么我的策略逻辑的执行会有延迟？

	*作者在开发的过程中发现，向CTP发送请求过于密集可能导致请求被”吞掉“，所以程序会将您发出的请求在放入队列中，依次发出，请求发送的间隔默认为1秒，这个间隔的设置会在后续版本中开放。*
* 为什么我在RQAlpha中查询到的账户、持仓信息与我通过快期、vn.trader 等终端查询到的不一致？

	*本 mod 会尽力将您的账户信息恢复至 RQAlpha 中，但由于计算逻辑的不同，可能会导致各个终端显示的数字有差异，另外您通过其他终端下单交易也有可能导致数据同步的不及时。不过这也有可能是程序bug，如果您发现不一致情况严重，欢迎通过Issue的方式向作者提出。*

* VN.PY 的环境配置和安装比较复杂，我搞不定／懒得搞怎么办？

	*作者会尽力研究，争取将VN.PY的安装包含进 mod 中，通过 pip 的形式一键安装，在这之前，作者会提供一个开箱即用虚拟机镜像，供您直接下载使用。*
	
## TODO

* rqalpha 和 VN.PY 开箱即用虚拟机
* 开放CTP请求执行间隔时间的设置
* rqalpha-mod-vnpy 的结构和数据流程图
* 解决CTP请求未响应导致的数据不完整问题
* 包含 VN.PY 或 vn.trader 的一键部署包
* 接入其他接口
