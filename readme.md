[English Version](#english-version)

不支持除了GET以外的方法使用多线程下载  
不推荐用于日常浏览器使用, 有些功能可能不支持  
它不是那么稳定, 可能会导致一些东西失效, 莫名其妙404, 500, SSL Handshake Error等错误等, 所以如果出事了, 先把这个关掉  

它可以通过 --with-cache 参数开启缓存, 默认会对一些特定文件上24小时缓存, 详情见configs.py  
你可以通过 --with-history 参数开启历史记录, 它会记录流量, 然后默认在关闭时dump到/log  

参考init.py来导入ca证书  
注意, ca证书导入是可选项, 当且仅当你想要它作为系统代理的时候才需要使用, 而且它比较危险, 建议使用过后删除  

cacerts是你从你的java home/lib/security目录下找到的证书文件，truststore.jks是你自己创建的信任库文件, 给gradle用的  
记得用gradle对应的java home  
记得重启你的IDE  

```bash
keytool -importcert -alias do_not_trust_multithread_downloading_proxy_ca -file ca_server.crt -keystore truststore.jks -storepass changeit -noprompt
keytool -importkeystore -srckeystore cacerts -destkeystore truststore.jks -srcstorepass changeit -deststorepass changeit -noprompt
```

<a id="english-version"></a>
## English Version

The multi-thread downloading proxy only supports GET method. Other HTTP methods are not supported.  
Not recommended for daily browser use as some features may not work properly.  
It's quite unstable and may cause failures, random 404/500 errors, SSL handshake errors, etc. If any issue occurs, disable it immediately.  

Cache can be enabled with --with-cache parameter. By default it sets 24-hour cache for certain files, see configs.py for details.  
History can be enabled with --with-history parameter. It records traffic and dumps it to /log when closed.  

Refer to init.py to import CA certificates.  
Note: CA certificate import is optional and only required when using as system proxy. It's potentially dangerous - recommended to remove after use.  

cacerts is the certificate file from your java home/lib/security directory. truststore.jks is the truststore file you created for gradle.  
Make sure to use the java home corresponding to your gradle installation.  
Don't forget to restart your IDE after configuration.  

```bash
keytool -importcert -alias do_not_trust_multithread_downloading_proxy_ca -file ca_server.crt -keystore truststore.jks -storepass changeit -noprompt
keytool -importkeystore -srckeystore cacerts -destkeystore truststore.jks -srcstorepass changeit -deststorepass changeit -noprompt
```