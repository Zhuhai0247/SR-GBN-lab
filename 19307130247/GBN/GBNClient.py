import socket
import select
import re
import time
from random import random

from Helper import Helper

# *************************************************************************************************************
# GBNClient实现思路：根据FSMs
#
# 发送方：等待 ---> base = 1, nextseqnum = 1 --->
#   情况1 rdt_send(data) :
# 	if( nextseqnum < base + N ){
# 		sndpkt[ nextseqnum ] = make_pkt( nextseqnum , data , checksum )
# 		udt_send( sndpkt[ nextseqnum ])
# 		if (base == nextseqnum) start_timer
# 		    nextseqnum ++}
# 		else refuse_data( data )
#
# 	情况2 time_out :
# 		start_timer
# 		udt_send( sndpkt[base] ) -> udt_send( sndpkt[base+1] ) -> … -> udt_send( sndpkt[ nextseqnum-1])
#
# 	情况3 rdt_rcv(rcvpkt) && notcorrupt(rcvpkt) :
# 		base = getacknum(rcvpkt) + 1
# 		if(base == nextseqnum) stop_timer //如果接收方发的是正确的ack，则会满足等式
# 		else start_timer
#
# 	情况4 rdt_rcv(rcvpkt) && corrupt(rcvpkt) ---> continue
#
#   实际上，为了实现双向传输，也实现了Server的算法
# *************************************************************************************************************


class GBNClient:
    def __init__(self):
        # self.base = 1           窗口开头不再需要，python可以简化地直接移动数组
        self.nextseqnum = 1     # 待发送数据下标
        self.max_time = 5       # 超时时间
        self.wait_time = 15     # 等待数据发送时间
        self.window = []        # 滑动窗口
        self.rev_data = ''      # 接收数据

        self.fd_num = 0        # 发送包的数量
        self.N = 3              # 窗口大小

        self.addr = ('127.0.0.1',7777)                                  # client地址和端口
        self.server_addr = ('127.0.0.1',17777)                          # server地址和端口
        self.socket = socket.socket(socket.AF_INET,socket.SOCK_DGRAM)   # socket初始化，根据报告要求，用IPv4，UDP
        self.socket.bind(self.addr)                                     # socket绑定

        self.timer = 0
        self.add_condition = 0
        self.add_window = 0
        self.origin_N = 3

    def send(self,buffer):
        fd_timer = 0                # 超时计时器
        data_timer = 0              # 等待计时器
        self.fd_num = len(buffer)   # 初始化包序号
        last_ack = 0                # 最新的ACK

        while True :
            time.sleep(0.5)
            self.N = self.add_window + self.origin_N
            self.timer += 1
            print(self.timer,':当前滑动窗口大小为：',self.N)
            # 以下是client算法
            while len(self.window) < self.N:        # 情况1:窗口未满，将数据放入，这里为了方便，和超时数据在最后一起发送
                if self.nextseqnum > self.fd_num:  # 如果待发序列大小已经大于包数量，则break
                    break
                data = Helper(buffer[self.nextseqnum - 1],0,
                              seq=self.nextseqnum)  # 封装数据报
                self.window.append(data)            # 添加到窗口
                self.nextseqnum += 1                # 序列号增加

            if fd_timer > self.max_time:            # 情况2：time out
                self.add_window =int(self.add_window/2)
                resend = []                         # 重传窗口
                for data in self.window:            # 以下为重传实现，使is_ack为0即可
                    data.is_send = 0
                    resend.append(data.seq)
                if len(resend) > 0:
                    print('client:超时！重传:', resend)

            if not self.window:                     # 退出条件：窗口为空
                if fd_timer > self.max_time and data_timer > self.wait_time:
                    with open('creceive.txt','wb') as f :
                        f.write(self.rev_data.encode())
                        print('client:发送/接收成功！')
                        break

            for data in self.window:                # 将情况1、2的数据都发出去
                if not data.is_send :
                    print('client:发送数据，序号为:',data.seq)
                    self.socket.sendto(str(data).encode(), self.server_addr)
                    data.is_send = 1

            # 以下是client和server算法的结合
            read_fd, write_fd, error_fd = select.select([self.socket, ], [], [], 1)     # 利用select模块进行无阻塞的socket连接

            if len(read_fd) > 0:                                 # 情况3、4：收到回复
                msg, addr = self.socket.recvfrom(1024)           # 接收报文
                msg = msg.decode()                               # 处理报文
                list = re.split(r'\W',msg,2)
                temp_seq = list[0]
                temp_ack = list[1]
                temp_data = list[2]
                if temp_ack == '1':                                # 情况3：收到ACK
                    fd_timer = 0                                   # 统一为情况1、2重置计时器
                    print('client:收到ACK，序号为', temp_seq)       # 显示序列号
                    ack_num = temp_seq
                    for i in range(len(self.window)):            # 判断序号号是否正确
                        if ack_num == self.window[i].seq:
                            self.window = self.window[i+1:]      # 正确，window后移
                            self.add_condition += 1
                            if self.add_condition == self.N:
                                self.add_window += 1
                                self.add_condition = 0
                            break                                # 错误，退出
                else:
                    fd_timer += 1                                # 没有收到ACK，计时器增加
                    print('client:收到数据，序号为: ',temp_seq)        # 那就是收到了对方发来的数据
                    ack_num = int(temp_seq)
                    data_timer = 0                               # 重置data计时器
                    if last_ack == ack_num - 1:                  # 如果是期望的数据
                        if random() < 0.2:                       # 模拟丢包/ACK,概率20%
                            if random() < 0.5:
                                print('client:模拟数据丢失，丢失序列号:',ack_num)
                                continue
                            else:
                                print('client:模拟ACK丢失，丢失序列号:',ack_num)
                                last_ack = ack_num
                                self.rev_data += temp_data
                                continue
                        self.socket.sendto(str(Helper(''.encode(),1,ack_num)).encode(), addr)
                        print('client:发送ACK，序号为:',ack_num)
                        last_ack = ack_num
                        self.rev_data += temp_data
                    else:
                        print('client:收到错误数据，发送最大ACK:',last_ack)                    # 收到了重复的或者不期望的未来数据包
                        self.socket.sendto(str(Helper(''.encode(),1,last_ack)).encode(),addr)   # 发送最大ACK
            else:   # 未收到数据，计时器全部加1
                fd_timer += 1
                data_timer += 1

    def start(self):    # 启动函数
        buf = []
        with open('csend.txt','rb') as f:   # 打开发送文本
            while True:                     # 将文本读入buf中
                seq = f.read(100)           # buf中每个字符串为500长度（除了最后一个）
                if len(seq) > 0:
                    buf.append(seq)
                else:
                    break
        self.socket.sendto('GBN-TEST'.encode(),self.server_addr)    # 建立连接，发送特殊请求码
        self.send(buf)                                              # 发送数据


if __name__ == '__main__':
    client = GBNClient()
    client.start()


















