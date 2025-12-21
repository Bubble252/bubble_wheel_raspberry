def ConnectRelay(PORT):
 """
 此函数为连接串口继电器模块，为初始函数，必须先调用
 :param PORT: USB-串口端口，需要手动填写，须在计算机中手动查看对应端口
 :return: >0 连接成功，<0 连接超时
 """
 try:
 # c2s03 设备默认波特率 9600、偶校验、停止位 1
 master = modbus_rtu.RtuMaster(serial.Serial(port=PORT,
 baudrate=9600, bytesize=8,
parity='E', stopbits=1))
 master.set_timeout(5.0)
 master.set_verbose(True)
 # 读输入寄存器
 # c2s03 设备默认 slave=2, 起始地址=0, 输入寄存器个数 2
 master.execute(2, cst.READ_INPUT_REGISTERS, 0, 2)
 # 读保持寄存器
 # c2s03 设备默认 slave=2, 起始地址=0, 保持寄存器个数 1
 master.execute(2, cst.READ_HOLDING_REGISTERS, 0, 1) # 这里可以修改
需要读取的功能码
 # 没有报错，返回 1
 response_code = 1
 except Exception as exc:
 print(str(exc))
 # 报错，返回<0 并输出错误
 response_code = -1
 master = None
 return response_code,