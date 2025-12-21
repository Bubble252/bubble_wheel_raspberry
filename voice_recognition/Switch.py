def Switch(master, ACTION):
    """
    此函数为控制继电器开合函数，如果 ACTION=ON 则闭合，如果如果 ACTION=OFF 则断开。
    :param master: 485 主机对象，由 ConnectRelay 产生
    :param ACTION: ON 继电器闭合，开启风扇；OFF 继电器断开，关闭风扇。
    :return: >0 操作成功，<0 操作失败
    """
    try:
        if "on" in ACTION.lower():


# 写单个线圈，状态常量为 0xFF00，请求线圈接通
# c2s03 设备默认 slave=2, 线圈地址=0, 请求线圈接通即 output_value 不等于0
master.execute(2, cst.WRITE_SINGLE_COIL, 0, output_value=1)
else:
# 写单个线圈，状态常量为 0x0000，请求线圈断开
# c2s03 设备默认 slave=2, 线圈地址=0, 请求线圈断开即 output_value 等于0
master.execute(2, cst.WRITE_SINGLE_COIL, 0, output_value=0)
# 没有报错，返回 1
response_code = 1
except Exception as exc:
print(str(exc))
# 报错，返回<0 并输出错误
response_code = -1
return response_code