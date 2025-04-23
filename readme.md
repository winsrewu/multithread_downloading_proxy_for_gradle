[English Version](#english-version)

不支持除了GET以外的方法使用多线程下载, 如果涉及到了, 不要用这个, 或者提PR也行  
我支持了一点这些东西, 但是它依旧不能用于浏览器  
它非常不稳定, 可能会导致一些东西失效, 莫名其妙404, 500等错误等, 所以如果出事了, 先把这个关掉  

它默认会对一些特定文件上24小时缓存, 详情剪configs.py, 你可以通过 --no-cache 参数禁用缓存  

参考init.py来导入ca证书  

cacerts是你从你的java home/lib/security目录下找到的证书文件，truststore.jks是你自己创建的信任库文件, 给gradle用的  
记得用gradle对应的java home  
记得重启你的IDE  

```bash
keytool -importcert -alias do_not_trust_multithread_downloading_proxy_ca -file ca_server.crt -keystore truststore.jks -storepass changeit -noprompt
keytool -importkeystore -srckeystore cacerts -destkeystore truststore.jks -srcstorepass changeit -deststorepass changeit -noprompt
```

<a id="english-version"></a>
## English Version

Multi-thread downloading proxy only supports GET method. If other methods are involved, don't use this or submit a PR.  
Some features are supported but it still cannot be used in browsers.  
It's very unstable and may cause failures, random 404, 500 errors, etc. If something goes wrong, disable it first.  

By default it sets 24-hour cache for certain files, see configs.py for details. You can disable cache with --no-cache parameter.  

Refer to init.py to import CA certificates.  

cacerts is the certificate file from your java home/lib/security directory, truststore.jks is the truststore file you created for gradle.  
Remember to use the java home corresponding to gradle.  
Remember to restart your IDE.  

```bash
keytool -importcert -alias do_not_trust_multithread_downloading_proxy_ca -file ca_server.crt -keystore truststore.jks -storepass changeit -noprompt
keytool -importkeystore -srckeystore cacerts -destkeystore truststore.jks -srcstorepass changeit -deststorepass changeit -noprompt
```