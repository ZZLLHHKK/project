# 程式部分細節

## 錄音接口(USB麥克風設定)

首先，在樹莓派的終端機打入以下指令:

```
arecord -l
# 會出現 eg : plughw:3,0
```

到以下檔案修改函式參數:

```
config.py
把 `DEVICE_PORT` 改成你usb麥克風的接口
```
即可正常運行