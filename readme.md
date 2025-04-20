cacerts是你从你的java home/lib/security目录下找到的证书文件，truststore.jks是你自己创建的信任库文件, 给gradle用的
记得用gradle对应的java home

不支持除了GET以外的方法, 不支持请求头, 如果涉及到了, 不要用这个, 或者提PR也行

在generate_cert.py运行之后运行

```bash
keytool -importcert -alias server -file server.crt -keystore truststore.jks -storepass changeit -noprompt
keytool -importkeystore -srckeystore cacerts -destkeystore truststore.jks -srcstorepass changeit -deststorepass changeit -noprompt
```

不要重复运行generate_cert.py, 否则会覆盖之前的证书

generate_cert.py中
```python
x509.SubjectAlternativeName([
        DNSName("*.mojang.com"),
        DNSName("*.minecraft.net"),
        DNSName("*.jawbts.org"),
        DNSName("localhost"),
        IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]),
```
可以修改为你需要的涉及大文件的域名