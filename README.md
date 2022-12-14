# 基于UDP实现的可靠文件传输协议FDFTP



## 环境需求：

1.python3.6



## 设计文档：

设计文档在Docs文件夹下



## 使用方法：

1.在两台机器上部署好代码，分别将Common/Options内的SERVER_IP和CLIENT_IP修改为对应ip。

2.然后分别在服务器的Server文件夹下运行Server.py文件，在客户端的Client文件夹下运行Client.py。

3.在Client的界面输入upload 文件名 或 download 文件名 X   (X代表使用线程数量)或者使用exit命令退出

4.该服务支持多线程下载和单线程上传，输入指令时可以指定线程数，若不输入，则默认4个线程下载(可以在Common/Options.py内修改默认值)。



## 注意事项：

1.请确保要下载的文件在服务端的Server文件夹下，要上传的文件在客户端的Client文件夹下

2.如果要使用多个客户端连接同一个服务端，请确保多个客户端不要在同一个文件夹下下载同一文件，不然他们可能会互相覆盖已下载的文件

3.由于python thread库内的线程都是跑在单核上的，并不能保证使用的线程数越多下载速度越快(后续可能会改进为多核并行版本的)。在有一定丢包率的环境，单线程无法独自占满带宽的情况下，可以适当调大线程数，一般建议不超过8个线程。(设置最大线程数为16，可在Common/Options.py内修改最大线程数)

4.Server运行需要占据45678端口，请确保该端口空闲，或者可以在Common/Options.py文件内修改默认值

5.如果出现奇怪的通信错误，或者输入指令后立马结束而没有成功下载文件，请检查你设置的IP地址。(例如，客户端可能需要设置SERVER_IP为服务器的公网ip，而客户端和服务器只能监听自己的内网ip）

6.如果接收方打印出了successfully！则证明下载成功。如果出现md5 timeout的字样，也不要惊慌，只是接收方没有收到md5校验包，下载的文件大概率是正确的。如果出现file seems error的字样，那么说明md5校验错误，下载的文件可能是错误的，可能需要重新下载。

7.如果出现timeout的输出，请等个几秒再重新输入指令，或者直接重启服务端和客户端。如果出现其他奇怪的问题，请重启服务端和客户端。